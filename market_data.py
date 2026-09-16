"""
Market Data Module
==================

Reads public BTC market data from Coinbase.

PAPER TRADING ONLY:
- No API keys
- No private keys
- No wallet
- No real orders
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests


COINBASE_TICKER_URL = (
    "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
)

COINBASE_CANDLES_URL = (
    "https://api.exchange.coinbase.com/products/BTC-USD/candles"
)

FIVE_MINUTES = 5 * 60


@dataclass
class MarketData:
    btc_open: float
    btc_current: float
    window_start: int
    window_end: int
    seconds_remaining: int


def get_btc_current_price() -> float:
    """
    Get current BTC/USD price from Coinbase.
    """

    response = requests.get(
        COINBASE_TICKER_URL,
        timeout=10,
        headers={
            "User-Agent": "polymarket-btc-paper-trader/1.0"
        },
    )

    response.raise_for_status()

    data = response.json()

    return float(data["price"])


def get_current_5m_window() -> tuple[int, int, int]:
    """
    Calculate the current 5-minute UTC window.
    """

    now = int(time.time())

    window_start = (now // FIVE_MINUTES) * FIVE_MINUTES
    window_end = window_start + FIVE_MINUTES

    seconds_remaining = max(0, window_end - now)

    return window_start, window_end, seconds_remaining


def get_btc_5m_open(window_start: int) -> float:
    """
    Get the opening BTC price of the current 5-minute candle.
    """

    window_end = window_start + FIVE_MINUTES

    response = requests.get(
        COINBASE_CANDLES_URL,
        params={
            "granularity": FIVE_MINUTES,
            "start": datetime.fromtimestamp(
                window_start,
                tz=timezone.utc,
            ).isoformat(),
            "end": datetime.fromtimestamp(
                window_end,
                tz=timezone.utc,
            ).isoformat(),
        },
        timeout=10,
        headers={
            "User-Agent": "polymarket-btc-paper-trader/1.0"
        },
    )

    response.raise_for_status()

    candles = response.json()

    if not candles:
        raise ValueError("No 5-minute candle data returned.")

    # Coinbase candle format:
    # [timestamp, low, high, open, close, volume]

    current_candle = None

    for candle in candles:
        candle_timestamp = int(candle[0])

        if candle_timestamp == window_start:
            current_candle = candle
            break

    if current_candle is None:
        raise ValueError(
            "Current 5-minute candle was not found."
        )

    return float(current_candle[3])


def get_market_data() -> MarketData:
    """
    Get current BTC price and current 5-minute opening price.
    """

    window_start, window_end, seconds_remaining = (
        get_current_5m_window()
    )

    btc_open = get_btc_5m_open(window_start)

    btc_current = get_btc_current_price()

    return MarketData(
        btc_open=btc_open,
        btc_current=btc_current,
        window_start=window_start,
        window_end=window_end,
        seconds_remaining=seconds_remaining,
    )


def format_timestamp(timestamp: int) -> str:
    """
    Convert Unix timestamp to readable UTC time.
    """

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).strftime("%Y-%m-%d %H:%M:%S UTC")


def calculate_btc_move_pct(
    btc_open: float,
    btc_current: float,
) -> float:
    """
    Calculate BTC percentage movement from candle open.
    """

    if btc_open <= 0:
        raise ValueError("BTC opening price must be positive.")

    return (
        (btc_current - btc_open)
        / btc_open
        * 100
    )


def print_market_data(data: MarketData) -> None:
    """
    Print live BTC market data.
    """

    move_pct = calculate_btc_move_pct(
        data.btc_open,
        data.btc_current,
    )

    print("=" * 60)
    print("BTC MARKET DATA")
    print("=" * 60)

    print(f"BTC 5m Open:       ${data.btc_open:,.2f}")
    print(f"BTC Current:       ${data.btc_current:,.2f}")

    print(
        f"BTC Movement:      {move_pct:+.4f}%"
    )

    print(
        f"5m window start:   "
        f"{format_timestamp(data.window_start)}"
    )

    print(
        f"5m window end:     "
        f"{format_timestamp(data.window_end)}"
    )

    print(
        f"Seconds remaining: {data.seconds_remaining}"
    )

    print("=" * 60)
    print("PAPER MODE")
    print("NO REAL TRADING")
    print("NO API KEYS")
    print("NO WALLET")
    print("=" * 60)


def run_test() -> None:
    """
    Test live public BTC market data.
    """

    print(
        "Connecting to Coinbase public BTC market data..."
    )

    try:
        data = get_market_data()

        print_market_data(data)

    except requests.RequestException as error:
        print()
        print(
            "ERROR: Could not retrieve Coinbase market data."
        )
        print(error)

    except (
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ) as error:
        print()
        print(
            "ERROR: Unexpected market data response."
        )
        print(error)


if __name__ == "__main__":
    run_test()
