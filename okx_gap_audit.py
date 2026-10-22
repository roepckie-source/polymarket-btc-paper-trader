#!/usr/bin/env python3
"""Read-only audit of the OKX BTC-USDT 5m candle gap in a paper-trading state.

This script only reads the local state file and public OKX market data. It does
not edit state, trades, balances, positions, or halt flags.
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

BASE_URL = "https://www.okx.com/api/v5/market/candles"
BAR_MS = 5 * 60 * 1000


def iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def fetch_candles(end_ms: int, limit: int = 300) -> list[list[str]]:
    # OKX's `after` pagination returns candles older than the supplied timestamp.
    params = urllib.parse.urlencode({
        "instId": "BTC-USDT", "bar": "5m", "after": str(end_ms + BAR_MS), "limit": str(limit)
    })
    req = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={"User-Agent": "okx-paper-gap-audit/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != "0":
        raise RuntimeError(f"OKX API error: code={payload.get('code')} msg={payload.get('msg')}")
    return payload.get("data", [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", help="Path to okx_paper_state.json (read-only)")
    parser.add_argument("--output", default="okx_gap_audit.csv", help="CSV report path (default: okx_gap_audit.csv)")
    parser.add_argument("--now-ms", type=int, default=None,
                        help="Optional fixed end timestamp in Unix ms for reproducible audits")
    args = parser.parse_args()

    state_path = Path(args.state)
    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    last_ts = int(state["last_candle_ts"])
    stop_price = float(state["stop_price"])
    end_ms = args.now_ms if args.now_ms is not None else int(time.time() * 1000)

    if state.get("halted"):
        print("STATE: halted=True (left unchanged)")
    print(f"Instrument: BTC-USDT | interval: 5m")
    print(f"Last processed candle: {iso(last_ts)}")
    print(f"Audit end time:        {iso(end_ms)}")
    print(f"Stored stop price:     {stop_price:.2f} USDT")
    print("Mode: READ-ONLY; state file will not be modified")

    raw = fetch_candles(end_ms)
    candles = []
    for row in raw:
        if len(row) < 9:
            continue
        ts = int(row[0])
        # Only fully closed candles, strictly after the last processed candle.
        if last_ts < ts <= end_ms and row[8] == "1":
            candles.append({
                "timestamp_ms": ts, "timestamp_utc": iso(ts),
                "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]),
                "volume": float(row[5]), "confirm": row[8],
            })
    candles.sort(key=lambda c: c["timestamp_ms"])
    unique = {c["timestamp_ms"]: c for c in candles}
    candles = [unique[k] for k in sorted(unique)]

    # The candle whose open time is in the current 5m bucket is still forming.
    last_closed_open_ms = (end_ms // BAR_MS) * BAR_MS - BAR_MS
    expected = list(range(last_ts + BAR_MS, last_closed_open_ms + 1, BAR_MS))
    got = {c["timestamp_ms"] for c in candles}
    missing = [t for t in expected if t not in got]
    stop_hits = [c for c in candles if c["low"] <= stop_price]

    out = Path(args.output)
    fields = ["timestamp_ms", "timestamp_utc", "open", "high", "low", "close", "volume", "confirm"]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candles)

    print(f"Closed candles retrieved in gap: {len(candles)}")
    print(f"Expected 5m candle timestamps:   {len(expected)}")
    print(f"Missing expected timestamps:     {len(missing)}")
    if missing:
        print("First missing: ", iso(missing[0]))
        print("Last missing:  ", iso(missing[-1]))
    print(f"Candles with low <= stop:        {len(stop_hits)}")
    if stop_hits:
        for c in stop_hits:
            print(f"STOP LEVEL TOUCHED/BELOW: {c['timestamp_utc']} low={c['low']:.2f} close={c['close']:.2f}")
    elif candles:
        min_candle = min(candles, key=lambda c: c["low"])
        print(f"Lowest retrieved low: {min_candle['low']:.2f} at {min_candle['timestamp_utc']}")
    else:
        print("WARNING: no candles found in the requested gap; audit is inconclusive")

    print(f"CSV report written: {out.resolve()}")
    print("IMPORTANT: no state reset, no halt override, no trade replay was performed.")
    if missing or not candles:
        print("RESULT: INCONCLUSIVE — do not resume the paper trader yet.")
        return 2
    if stop_hits:
        print("RESULT: STOP LEVEL WAS REACHED IN AT LEAST ONE 5m CANDLE — keep halted; inspect intrabar execution rules.")
        return 3
    print("RESULT: no retrieved 5m candle low crossed the stored stop. This alone does not authorize resuming; reconcile the state and exact candle coverage first.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
