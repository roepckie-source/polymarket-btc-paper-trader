"""Public OKX candle data for the BTC spot paper trader. No private API or orders."""
from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://www.okx.com/api/v5/market/candles"


def _instrument_id(instrument: str) -> str:
    value = str(instrument).strip().upper().replace("/", "-").replace("_", "-")
    if not value or "-" not in value:
        raise ValueError(f"Invalid OKX instrument {instrument!r}; expected BTC-USDT or BTC/USDT")
    return value


def fetch_candles(instrument: str, bar: str, limit: int) -> list[dict]:
    """Return confirmed candles oldest-first with ts/open/high/low/close fields.

    OKX public market endpoint only. The currently forming candle is excluded so
    the paper strategy only evaluates completed bars.
    """
    inst_id = _instrument_id(instrument)
    bar = str(bar).strip()
    if not bar:
        raise ValueError("bar must not be empty")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 300:
        raise ValueError("limit must be an integer from 1 to 300 for the OKX candles endpoint")

    query = urlencode({"instId": inst_id, "bar": bar, "limit": str(limit)})
    request = Request(
        f"{BASE_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "BTC-Spot-Paper-Trader/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"OKX candle API returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach public OKX candle API: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("OKX candle API returned invalid JSON") from exc

    if not isinstance(payload, dict) or payload.get("code") != "0":
        code = payload.get("code", "unknown") if isinstance(payload, dict) else "invalid-response"
        message = payload.get("msg", "unknown API error") if isinstance(payload, dict) else "response was not an object"
        raise RuntimeError(f"OKX candle API error {code}: {message}")

    raw = payload.get("data")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"OKX returned no candles for {inst_id} {bar}")

    candles = []
    now_ms = int(time.time() * 1000)
    for row in raw:
        # OKX fields: ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm
        if not isinstance(row, list) or len(row) < 9:
            raise RuntimeError("Unexpected OKX candle row format")
        if str(row[8]) != "1":
            continue  # skip the still-forming candle
        candle = {
            "ts": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        }
        if candle["ts"] > now_ms:
            raise RuntimeError("OKX returned a candle timestamp in the future")
        if any(not (v > 0 and v < float("inf")) for k, v in candle.items() if k != "ts"):
            raise RuntimeError("OKX returned a non-finite or non-positive candle price")
        candles.append(candle)

    candles.sort(key=lambda c: c["ts"])
    unique = []
    seen = set()
    for candle in candles:
        if candle["ts"] not in seen:
            unique.append(candle)
            seen.add(candle["ts"])
    if not unique:
        raise RuntimeError("OKX returned no confirmed candles; refusing to evaluate paper strategy")
    return unique


if __name__ == "__main__":
    sample = fetch_candles("BTC-USDT", "5m", 30)
    print(f"OKX public data PASS: {len(sample)} confirmed candles")
    print(f"Oldest: {sample[0]}")
    print(f"Latest: {sample[-1]}")
