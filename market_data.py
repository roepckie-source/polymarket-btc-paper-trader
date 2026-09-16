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


COINBASE_URL = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"

FIVE_MINUTES = 5 * 60


@dataclass
class MarketData:
    btc_price: float
    window_start: int
    window_end: int
    seconds_remaining: int


def get_btc_price() -> float:
    """
    Get current BTC/USD price from Coinbase public API.
    """

    response = requests.get(
        COINBASE_URL,
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

    Returns:
        window_start
        window_end
        seconds_remaining
    """

    now = int(time.time())

    window_start = (now // FIVE_MINUTES) * FIVE_MINUTES
    window_end = window_start + FIVE_MINUTES

    seconds_remaining = max(0, window_end - now)

    return window_start, window_end, seconds_remaining


def get_market_data() -> MarketData:
    """
    Get the current BTC price and 5-minute market window.
    """

    btc_price = get_btc_price()

    window_start, window_end, seconds_remaining = (
        get_current_5m_window()
    )

    return MarketData(
        btc_price=btc_price,
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


def print_market_data(data: MarketData) -> None:
    """
    Print market data in a readable format.
    """

    print("=" * 50)
    print("BTC MARKET DATA")
    print("=" * 50)

    print(f"BTC/USD:          ${data.btc_price:,.2f}")

    print(
        f"5m window start:  {format_timestamp(data.window_start)}"
    )

    print(
        f"5m window end:    {format_timestamp(data.window_end)}"
    )

    print(
        f"Seconds remaining: {data.seconds_remaining}"
    )

    print("=" * 50)
    print("PAPER MODE")
    print("NO REAL TRADING")
    print("=" * 50)


def run_test() -> None:
    """
    Simple live public-data test.
    """

    print("Connecting to Coinbase public market data...")

    try:
        data = get_market_data()

        print_market_data(data)

    except requests.RequestException as error:
        print()
        print("ERROR: Could not retrieve Coinbase market data.")
        print(error)

    except (KeyError, ValueError, TypeError) as error:
        print()
        print("ERROR: Unexpected Coinbase response.")
        print(error)


if __name__ == "__main__":
    run_test()
