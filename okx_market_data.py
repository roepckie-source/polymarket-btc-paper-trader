"""Public OKX candle reader only; never submits orders."""
from __future__ import annotations
import os
import requests

BASE_URL = os.getenv("OKX_PUBLIC_BASE_URL", "https://eea.okx.com")

def fetch_candles(inst_id="BTC-USDT", bar="5m", limit=100, session=None):
    client = session or requests
    url = f"{BASE_URL}/api/v5/market/candles"
    response = client.get(url, params={"instId": inst_id, "bar": bar, "limit": str(limit)}, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "0":
        raise RuntimeError(f"OKX API error: {payload.get('code')} {payload.get('msg')}")
    rows = payload.get("data", [])
    # OKX rows: ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm
    parsed = []
    for row in rows:
        if len(row) >= 9:
            parsed.append({
                "ts": int(row[0]), "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]),
                "confirmed": row[8] == "1"
            })
    # API commonly returns newest first; normalize to oldest first.
    parsed.sort(key=lambda x: x["ts"])
    # Only use fully closed candles to avoid look-ahead / changing signals.
    return [c for c in parsed if c["confirmed"]]
