
#!/usr/bin/env python3
"""Read-only isolated replay of the OKX BTC-USDT paper-trader gap.

Uses the existing strategy and a copied state in memory.
Never writes the original paper state or trade log.
No private API, wallet, or orders.
"""

from __future__ import annotations

import copy
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from okx_spot_paper import step, validate_state, equity
from okx_paper_config import (
    INSTRUMENT,
    BAR,
    FEE_RATE,
    MAX_RISK_QUOTE,
    MAX_POSITION_QUOTE,
    STOP_DISTANCE,
)

STATE_FILE = Path("okx_paper_state.json")
OUTPUT_FILE = Path("okx_replay_events.csv")

BASE_URL = "https://www.okx.com/api/v5/market/history-candles"
BAR_MS = 300_000
PAGE_LIMIT = 300
MAX_PAGES = 100


def fetch_page(before_ms: int) -> list[list[str]]:
    params = urllib.parse.urlencode({
        "instId": INSTRUMENT,
        "bar": BAR,
        "after": str(before_ms),
        "limit": str(PAGE_LIMIT),
    })
    request = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "OKX-Paper-Replay-Audit/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict) or payload.get("code") != "0":
        raise RuntimeError(f"OKX API error: {payload}")

    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("Unexpected OKX candle response")

    return data


def row_to_candle(row: list[str]) -> dict | None:
    if len(row) < 9 or str(row[8]) != "1":
        return None

    candle = {
        "ts": int(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
    }

    for key in ("open", "high", "low", "close"):
        value = candle[key]
        if not (0 < value < float("inf")):
            raise RuntimeError(f"Invalid candle price: {key}={value}")

    if candle["low"] > candle["high"]:
        raise RuntimeError("Invalid candle: low exceeds high")

    if not candle["low"] <= candle["open"] <= candle["high"]:
        raise RuntimeError("Invalid candle: open outside low/high")

    if not candle["low"] <= candle["close"] <= candle["high"]:
        raise RuntimeError("Invalid candle: close outside low/high")

    return candle


def fetch_history(last_ts: int, end_ms: int) -> list[dict]:
    """Fetch closed candles backwards until cursor and EMA warm-up exist."""
    latest_closed = (end_ms // BAR_MS) * BAR_MS - BAR_MS
    cursor = latest_closed + BAR_MS
    by_ts: dict[int, dict] = {}
    pages = 0

    # Need the saved cursor, all subsequent candles, and >=22 prior candles
    # to provide enough EMA signal history before the cursor.
    required_prior = 22

    while pages < MAX_PAGES:
        rows = fetch_page(cursor)
        pages += 1

        if not rows:
            break

        timestamps = []

        for row in rows:
            candle = row_to_candle(row)
            if candle is None:
                continue

            ts = candle["ts"]
            timestamps.append(ts)

            if ts <= latest_closed:
                by_ts[ts] = candle

        if not timestamps:
            break

        oldest = min(timestamps)

        prior_count = sum(
            1 for ts in by_ts
            if ts < last_ts
        )

        if oldest <= last_ts and prior_count >= required_prior:
            break

        if oldest >= cursor:
            raise RuntimeError(
                "Historical pagination did not move backward."
            )

        cursor = oldest
        time.sleep(0.15)

    if pages >= MAX_PAGES:
        raise RuntimeError("Maximum pagination reached; replay incomplete.")

    candles = [by_ts[ts] for ts in sorted(by_ts)]

    if not candles:
        raise RuntimeError("No historical candles returned.")

    timestamps = [int(c["ts"]) for c in candles]

    if last_ts not in timestamps:
        raise RuntimeError(
            "Saved candle cursor is absent from fetched history."
        )

    cursor_index = timestamps.index(last_ts)

    if cursor_index < required_prior:
        raise RuntimeError(
            "Insufficient pre-cursor history for EMA warm-up."
        )

    # Check every candle in the replay interval is consecutive.
    replay = candles[cursor_index:]

    for previous, current in zip(replay, replay[1:]):
        if int(current["ts"]) - int(previous["ts"]) != BAR_MS:
            raise RuntimeError(
                "Replay gap: "
                f"{previous['ts']} -> {current['ts']}. "
                "Do not resume the paper trader."
            )

    if int(replay[-1]["ts"]) != latest_closed:
        raise RuntimeError(
            "Latest fully closed candle is missing; replay incomplete."
        )

    return candles


def main() -> int:
    if not STATE_FILE.exists():
        raise RuntimeError(f"Missing {STATE_FILE}")

    original = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    original = validate_state(copy.deepcopy(original))

    if not original.get("halted"):
        raise RuntimeError(
            "Expected halted state; refusing replay on an active state."
        )

    if original.get("last_candle_ts") is None:
        raise RuntimeError("Saved candle cursor is empty.")

    last_ts = int(original["last_candle_ts"])
    stop_price = float(original["stop_price"])
    end_ms = int(time.time() * 1000)
    latest_closed = (end_ms // BAR_MS) * BAR_MS - BAR_MS

    print("OKX PAPER REPLAY AUDIT")
    print("READ ONLY — NO ORDERS — NO STATE RESET")
    print(f"Instrument: {INSTRUMENT} | {BAR}")
    print(f"Saved cursor: {last_ts}")
    print(f"Last closed candle: {latest_closed}")
    print(f"Saved stop price: {stop_price:.2f} USDT")
    print(f"Saved halted: {original['halted']}")

    candles = fetch_history(last_ts, end_ms)
    cursor_index = next(
        i for i, candle in enumerate(candles)
        if int(candle["ts"]) == last_ts
    )
    replay = candles[cursor_index:]

    print(f"Total candles with warm-up: {len(candles)}")
    print(f"Candles in replay interval: {len(replay)}")

    # Independent stop-level cross-check before running strategy logic.
    stop_hits = [
        candle for candle in replay[1:]
        if float(candle["low"]) <= stop_price
    ]
    print(f"Candles touching stored stop: {len(stop_hits)}")

    if stop_hits:
        for candle in stop_hits:
            print(
                f"STOP LEVEL TOUCHED: ts={candle['ts']} "
                f"low={candle['low']:.2f}"
            )

    # Clear the halt only on an isolated in-memory copy.
    simulated = copy.deepcopy(original)
    simulated["halted"] = False
    simulated["halt_reason"] = None
    simulated["halted_at_utc"] = None

    simulated, result = step(
        simulated,
        candles,
        fee_rate=FEE_RATE,
        max_risk=MAX_RISK_QUOTE,
        max_position=MAX_POSITION_QUOTE,
        stop_distance=STOP_DISTANCE,
    )

    events = result.get("events", [result])
    fields = [
        "action",
        "candle_ts",
        "price",
        "btc",
        "notional_usdt",
        "fee_usdt",
        "realized_pnl_usdt",
        "reason",
    ]

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for event in events:
            writer.writerow({
                field: event.get(field, "")
                for field in fields
            })

    final_price = float(replay[-1]["close"])

    print()
    print("ISOLATED REPLAY RESULT")
    print(f"Events returned: {len(events)}")
    print(f"Final action: {result.get('action')}")
    print(f"Final reason: {result.get('reason')}")
    print(f"Simulated cash: {simulated['cash_usdt']:.8f} USDT")
    print(f"Simulated BTC: {simulated['btc']:.12f}")
    print(f"Final mark price: {final_price:.2f} USDT")
    print(f"Simulated equity: {equity(simulated, final_price):.8f} USDT")
    print(f"Simulated halted: {simulated.get('halted')}")
    print(f"Event CSV: {OUTPUT_FILE.resolve()}")
    print("Original state: NOT MODIFIED")
    print("Original trade log: NOT MODIFIED")
    print("Real orders: NONE")

    print()
    print(
        "IMPORTANT: This is a diagnostic replay, not authorization "
        "to resume the paper trader."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REPLAY ABORTED: {exc}", file=sys.stderr)
        raise SystemExit(1)
