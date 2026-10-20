"""Public OKX candle reader only. No authentication and no order endpoints."""
import os
import requests

BASE_URL = os.getenv("OKX_PUBLIC_BASE_URL", "https://eea.okx.com")

def fetch_candles(inst_id="BTC-USDT", bar="5m", limit=100, session=None):
    client = session or requests
    response = client.get(
        f"{BASE_URL}/api/v5/market/candles",
        params={"instId": inst_id, "bar": bar, "limit": str(limit)},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "0":
        raise RuntimeError(f"OKX API error: {payload.get('code')} {payload.get('msg')}")
    parsed = []
    for row in payload.get("data", []):
        if len(row) < 9:
            continue
        parsed.append({
            "ts": int(row[0]), "open": float(row[1]), "high": float(row[2]),
            "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]),
            "confirmed": row[8] == "1",
        })
    parsed.sort(key=lambda candle: candle["ts"])
    return [candle for candle in parsed if candle["confirmed"]]
