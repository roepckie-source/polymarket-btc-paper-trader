OKX BTC paper-trader gap audit (read-only)

Purpose:
- Fetch public OKX BTC-USDT 5-minute candles for the gap after last_candle_ts.
- Report missing expected closed candles and candles whose low touched/crossed stop_price.
- Write a CSV report.

Safety:
- Does not modify okx_paper_state.json or the trade log.
- Does not place orders and requires no API key.
- Do not clear the halted flag based only on this report; reconcile the state first.

Run locally from the repository root:
  python okx_gap_audit.py okx_paper_state.json --output okx_gap_audit.csv

The script needs internet access to the public OKX API. If the state file is elsewhere,
pass its actual path. Commit/upload the generated CSV only if you want it retained in GitHub.
