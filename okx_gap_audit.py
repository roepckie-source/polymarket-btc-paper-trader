
#!/usr/bin/env python3
"""Read-only audit of the OKX BTC-USDT 5m candle gap.

Reads the paper state and public OKX market data only.
Does NOT modify state, trades, balances, positions, or halt flags.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://www.okx.com/api/v5/market/history-candles"
BAR_MS = 5 * 60 * 1000
LIMIT = 300
MAX_PAGES = 1000


def iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(
        ts_ms / 1000, tz=timezone.utc
    ).isoformat()


def fetch_page(before_ms: int, limit: int = LIMIT) -> list[list[str]]:
    """Fetch historical candles older than the supplied timestamp."""
    params = urllib.parse.urlencode({
        "instId": "BTC-USDT",
        "bar": "5m",
        "after": str(before_ms),
        "limit": str(limit),
    })

    request = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={
            "User-Agent": "okx-paper-gap-audit/1.1",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if payload.get("code") != "0":
        raise RuntimeError(
            f"OKX API error: code={payload.get('code')} "
            f"msg={payload.get('msg')}"
        )

    return payload.get("data", [])


def candle_from_row(row: list[str]) -> dict | None:
    if len(row) < 9:
        return None

    try:
        return {
            "timestamp_ms": int(row[0]),
            "timestamp_utc": iso(int(row[0])),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "confirm": str(row[8]),
        }
    except (ValueError, TypeError, IndexError):
        return None


def fetch_gap(
    last_ts: int,
    last_closed_open_ms: int,
) -> list[dict]:
    """Fetch closed candles in the gap, excluding the current candle."""
    candles_by_ts: dict[int, dict] = {}

    # OKX history pagination moves backwards through candle timestamps.
    cursor = last_closed_open_ms + BAR_MS
    previous_oldest = None

    for page_number in range(1, MAX_PAGES + 1):
        rows = fetch_page(cursor)

        if not rows:
            break

        page_timestamps = []

        for row in rows:
            candle = candle_from_row(row)
            if candle is None:
                continue

            ts = candle["timestamp_ms"]
            page_timestamps.append(ts)

            # CRITICAL FIX:
            # Never include a candle starting after the last fully closed
            # 5-minute candle, even if the API unexpectedly marks it confirmed.
            if (
                last_ts < ts <= last_closed_open_ms
                and candle["confirm"] == "1"
            ):
                candles_by_ts[ts] = candle

        if not page_timestamps:
            break

        oldest = min(page_timestamps)

        if oldest <= last_ts:
            break

        if oldest == previous_oldest:
            raise RuntimeError(
                "Pagination did not advance; audit is inconclusive."
            )

        previous_oldest = oldest
        cursor = oldest

        if len(rows) < LIMIT:
            break

        time.sleep(0.15)
    else:
        raise RuntimeError(
            f"Reached MAX_PAGES={MAX_PAGES}; audit is incomplete."
        )

    return [
        candles_by_ts[ts]
        for ts in sorted(candles_by_ts)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "state",
        help="Path to okx_paper_state.json (read-only)",
    )
    parser.add_argument(
        "--output",
        default="okx_gap_audit.csv",
        help="CSV report path",
    )
    parser.add_argument(
        "--now-ms",
        type=int,
        default=None,
        help="Optional fixed audit-end timestamp in Unix milliseconds",
    )
    args = parser.parse_args()

    state_path = Path(args.state)

    with state_path.open("r", encoding="utf-8") as file:
        state = json.load(file)

    last_ts = int(state["last_candle_ts"])
    stop_price = float(state["stop_price"])
    end_ms = (
        args.now_ms
        if args.now_ms is not None
        else int(time.time() * 1000)
    )

    if end_ms <= last_ts:
        print("ERROR: audit end time must be after last candle.")
        return 1

    # The current 5-minute bucket is not considered closed.
    current_bucket_open_ms = (end_ms // BAR_MS) * BAR_MS
    last_closed_open_ms = current_bucket_open_ms - BAR_MS

    if last_ts % BAR_MS != 0:
        print("ERROR: saved candle timestamp is not aligned to 5 minutes.")
        return 1

    if last_closed_open_ms <= last_ts:
        print("ERROR: no complete candle interval available to audit.")
        return 1

    print("Instrument: BTC-USDT | interval: 5m")
    print(f"Last processed candle: {iso(last_ts)}")
    print(f"Audit wall-clock time: {iso(end_ms)}")
    print(f"Last closed candle:    {iso(last_closed_open_ms)}")
    print(f"Stored stop price:     {stop_price:.2f} USDT")
    print(f"Stored halted flag:    {state.get('halted')!r}")
    print("Mode: READ-ONLY; state file will not be modified")

    candles = fetch_gap(last_ts, last_closed_open_ms)

    expected = list(range(
        last_ts + BAR_MS,
        last_closed_open_ms + 1,
        BAR_MS,
    ))

    got = {c["timestamp_ms"] for c in candles}
    missing = [ts for ts in expected if ts not in got]

    stop_hits = [
        c for c in candles
        if c["low"] <= stop_price
    ]

    # Reject any unexpected timestamp rather than silently accepting it.
    out_of_range = [
        c for c in candles
        if not last_ts < c["timestamp_ms"] <= last_closed_open_ms
    ]

    output_path = Path(args.output)
    fields = [
        "timestamp_ms",
        "timestamp_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "confirm",
    ]

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candles)

    print(f"Closed candles retrieved: {len(candles)}")
    print(f"Expected candle timestamps: {len(expected)}")
    print(f"Missing timestamps: {len(missing)}")
    print(f"Out-of-range candles: {len(out_of_range)}")

    if missing:
        print(f"First missing: {iso(missing[0])}")
        print(f"Last missing:  {iso(missing[-1])}")

    print(f"Candles with low <= stop: {len(stop_hits)}")

    if stop_hits:
        for candle in stop_hits:
            print(
                "STOP LEVEL TOUCHED/BELOW: "
                f"{candle['timestamp_utc']} "
                f"low={candle['low']:.2f} "
                f"close={candle['close']:.2f}"
            )
    elif candles:
        lowest = min(candles, key=lambda c: c["low"])
        print(
            f"Lowest retrieved low: {lowest['low']:.2f} "
            f"at {lowest['timestamp_utc']}"
        )
    else:
        print("WARNING: no candles found; audit is inconclusive")

    print(f"CSV report written: {output_path.resolve()}")
    print("No state reset, halt override, or trade replay was performed.")

    if missing or not candles or out_of_range:
        print("RESULT: INCONCLUSIVE — keep the paper trader halted.")
        return 2

    if stop_hits:
        print(
            "RESULT: STOP LEVEL REACHED in at least one candle. "
            "Keep halted and inspect execution rules."
        )
        return 3

    print(
        "RESULT: No retrieved candle low crossed the stored stop. "
        "This alone does not authorize resuming the paper trader."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
