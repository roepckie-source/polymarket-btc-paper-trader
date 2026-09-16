"""
Coinbase BTC 5-Minute Market Data

PAPER / READ-ONLY ONLY

- Public Coinbase API
- No API keys
- No wallet
- No private keys
- No orders
- No trading
"""

import time
from datetime import datetime, timezone

import requests


TICKER_URL = (
    "https://api.exchange.coinbase.com/"
    "products/BTC-USD/ticker"
)

CANDLES_URL = (
    "https://api.exchange.coinbase.com/"
    "products/BTC-USD/candles"
)

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


def get_5m_open(start_timestamp):
    """
    Get the opening price of the current
    5-minute Coinbase candle.

    Coinbase candle format:

    [
        timestamp,
        low,
        high,
        open,
        close,
        volume
    ]
    """

    end_timestamp = start_timestamp + FIVE_MINUTES

    start_dt = datetime.fromtimestamp(
        start_timestamp,
        timezone.utc,
    )

    end_dt = datetime.fromtimestamp(
        end_timestamp,
        timezone.utc,
    )

    params = {
        "granularity": FIVE_MINUTES,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
    }

    response = requests.get(
        CANDLES_URL,
        params=params,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError(
            "Unexpected market data response."
        )

    if not data:
        raise RuntimeError(
            "No 5-minute candle data returned."
        )

    # ----------------------------------------------------------
    # Parse all valid candles
    # ----------------------------------------------------------

    candles = []

    for candle in data:

        if not isinstance(candle, list):
            continue

        if len(candle) < 6:
            continue

        try:

            timestamp = int(candle[0])
            opening = float(candle[3])

            candles.append(
                {
                    "timestamp": timestamp,
                    "open": opening,
                }
            )

        except (TypeError, ValueError):

            continue

    if not candles:
        raise RuntimeError(
            "No valid 5-minute candles returned."
        )

    # ----------------------------------------------------------
    # Exact candle
    # ----------------------------------------------------------

    for candle in candles:

        if candle["timestamp"] == start_timestamp:

            return candle["open"]

    # ----------------------------------------------------------
    # Coinbase sometimes returns candles around the
    # requested interval. Select the closest candle,
    # but only if it is reasonably close.
    # ----------------------------------------------------------

    closest = min(
        candles,
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
        "No suitable 5-minute candle found."
    )


def get_market_data():

    start_timestamp, end_timestamp = (
        current_window()
    )

    current_price = get_current_price()

    try:

        btc_open = get_5m_open(
            start_timestamp
        )

        source = "Coinbase 5m candle"

    except Exception as candle_error:

        print()
        print(
            "WARNING: Coinbase 5m candle unavailable."
        )

        print(
            f"Reason: {candle_error}"
        )

        print(
            "Using current BTC price as temporary "
            "open fallback."
        )

        print()

        btc_open = current_price

        source = "Coinbase ticker fallback"

    # ----------------------------------------------------------
    # Calculate BTC movement
    # ----------------------------------------------------------

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


def run_test():

    print(
        "Connecting to Coinbase public BTC "
        "market data..."
    )

    data = get_market_data()

    print_market_data(data)

    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            run_test()
        )

    except requests.RequestException as exc:

        print()
        print(
            "COINBASE REQUEST ERROR"
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
