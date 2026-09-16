"""
BTC 5-Minute Market Data

PAPER / READ-ONLY ONLY

Primary 5-minute candle:
- Kraken public API

Current BTC price:
- Coinbase public API

- No API keys
- No wallet
- No private keys
- No orders
- No trading
"""

import time
from datetime import datetime, timezone

import requests


# ==========================================================
# COINBASE
# ==========================================================

TICKER_URL = (
    "https://api.exchange.coinbase.com/"
    "products/BTC-USD/ticker"
)


# ==========================================================
# KRAKEN
# ==========================================================

KRAKEN_OHLC_URL = (
    "https://api.kraken.com/0/public/OHLC"
)

KRAKEN_PAIR = "XBTUSD"


TIMEOUT = 10
FIVE_MINUTES = 300


def utc_now():
    return datetime.now(timezone.utc)


def current_window():
    """
    Return current 5-minute UTC window.
    """

    now = int(time.time())

    start = now - (now % FIVE_MINUTES)
    end = start + FIVE_MINUTES

    return start, end


# ==========================================================
# COINBASE CURRENT PRICE
# ==========================================================

def get_current_price():
    """
    Get current BTC/USD price from Coinbase ticker.
    """

    response = requests.get(
        TICKER_URL,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    price = data.get("price")

    if price is None:
        raise RuntimeError(
            "Coinbase ticker returned no price."
        )

    return float(price)


# ==========================================================
# KRAKEN 5-MINUTE OPEN
# ==========================================================

def get_5m_open(start_timestamp):
    """
    Get the opening price of the current
    5-minute BTC candle from Kraken.

    Kraken OHLC format:

    [
        timestamp,
        open,
        high,
        low,
        close,
        vwap,
        volume,
        count
    ]
    """

    params = {
        "pair": KRAKEN_PAIR,
        "interval": 5,
        "since": start_timestamp,
    }

    response = requests.get(
        KRAKEN_OHLC_URL,
        params=params,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    # ------------------------------------------------------
    # Kraken API error handling
    # ------------------------------------------------------

    errors = data.get("error", [])

    if errors:
        raise RuntimeError(
            "Kraken API error: "
            + ", ".join(str(error) for error in errors)
        )

    result = data.get("result")

    if not isinstance(result, dict):
        raise RuntimeError(
            "Unexpected Kraken response."
        )

    # Kraken normally returns XBTUSD.
    # Search the first list containing OHLC candles.
    candles = None

    for key, value in result.items():

        if key == "last":
            continue

        if isinstance(value, list):
            candles = value
            break

    if not candles:
        raise RuntimeError(
            "No 5-minute candle data returned by Kraken."
        )

    # ------------------------------------------------------
    # Parse candles
    # ------------------------------------------------------

    valid = []

    for candle in candles:

        if not isinstance(candle, list):
            continue

        if len(candle) < 8:
            continue

        try:

            timestamp = int(float(candle[0]))
            opening = float(candle[1])

            valid.append(
                {
                    "timestamp": timestamp,
                    "open": opening,
                }
            )

        except (TypeError, ValueError):

            continue

    if not valid:
        raise RuntimeError(
            "No valid Kraken 5-minute candles found."
        )

    # ------------------------------------------------------
    # Exact candle
    # ------------------------------------------------------

    for candle in valid:

        if candle["timestamp"] == start_timestamp:

            return candle["open"]


    # ------------------------------------------------------
    # Closest candle
    # ------------------------------------------------------

    closest = min(
        valid,
        key=lambda candle: abs(
            candle["timestamp"] - start_timestamp
        ),
    )

    distance = abs(
        closest["timestamp"] - start_timestamp
    )

    if distance <= FIVE_MINUTES:

        return closest["open"]


    raise RuntimeError(
        "No suitable Kraken 5-minute candle found."
    )


# ==========================================================
# COMPLETE MARKET DATA
# ==========================================================

def get_market_data():

    start_timestamp, end_timestamp = (
        current_window()
    )

    # Current price from Coinbase
    current_price = get_current_price()

    # 5-minute opening price from Kraken
    btc_open = get_5m_open(
        start_timestamp
    )

    source = "Kraken 5m candle + Coinbase ticker"

    if btc_open <= 0:
        raise RuntimeError(
            "Invalid BTC opening price."
        )

    movement = (
        (current_price - btc_open)
        / btc_open
        * 100
    )

    seconds_remaining = max(
        0,
        end_timestamp - int(time.time()),
    )

    return {
        "btc_open": btc_open,
        "btc_current": current_price,
        "movement_percent": movement,
        "window_start": start_timestamp,
        "window_end": end_timestamp,
        "seconds_remaining": seconds_remaining,
        "source": source,
    }


# ==========================================================
# PRINT
# ==========================================================

def print_market_data(data):

    start_dt = datetime.fromtimestamp(
        data["window_start"],
        timezone.utc,
    )

    end_dt = datetime.fromtimestamp(
        data["window_end"],
        timezone.utc,
    )

    print("=" * 60)
    print("BTC MARKET DATA")
    print("=" * 60)

    print(
        f"BTC 5m Open:       "
        f"${data['btc_open']:,.2f}"
    )

    print(
        f"BTC Current:       "
        f"${data['btc_current']:,.2f}"
    )

    print(
        f"BTC Movement:      "
        f"{data['movement_percent']:+.4f}%"
    )

    print(
        f"5m window start:   "
        f"{start_dt}"
    )

    print(
        f"5m window end:     "
        f"{end_dt}"
    )

    print(
        f"Seconds remaining: "
        f"{data['seconds_remaining']}"
    )

    print(
        f"Data source:       "
        f"{data['source']}"
    )

    print("=" * 60)
    print("PAPER MODE")
    print("NO REAL TRADING")
    print("NO API KEYS")
    print("NO WALLET")
    print("=" * 60)


# ==========================================================
# TEST
# ==========================================================

def run_test():

    print(
        "Connecting to Kraken + Coinbase "
        "public BTC market data..."
    )

    data = get_market_data()

    print_market_data(data)

    return 0


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    try:

        raise SystemExit(
            run_test()
        )

    except requests.RequestException as exc:

        print()
        print(
            "MARKET DATA REQUEST ERROR"
        )

        print(exc)

        raise SystemExit(1)

    except Exception as exc:

        print()
        print(
            "ERROR:"
        )

        print(exc)

        raise SystemExit(1)
