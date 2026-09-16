"""
Polymarket BTC 5-Minute PAPER LIVE SIGNAL ENGINE

PAPER / READ-ONLY ONLY

- Uses live public Coinbase BTC data
- Uses live public Polymarket market data
- Uses strategy.py for signal evaluation
- NO API keys
- NO wallet
- NO private keys
- NO real orders
- NO real trading
"""

import time
from datetime import datetime, timezone

from market_data import get_market_data as get_coinbase_data
from polymarket_data import get_market_data as get_polymarket_data
from strategy import evaluate


# ============================================================
# CONFIGURATION
# ============================================================

PAPER_BANKROLL = 100.00

LOOP_INTERVAL_SECONDS = 10

# Same conservative volatility assumption
# currently used by strategy.py.
DAILY_VOLATILITY = 0.04


# ============================================================
# HELPERS
# ============================================================

def utc_now():
    """
    Return current UTC time.
    """

    return datetime.now(
        timezone.utc
    )


def get_market_price(
    polymarket_data,
    side,
):
    """
    Return the Polymarket price for the
    requested side.

    Expected outcomes:
        UP / DOWN
        or
        Up / Down

    Returns None if the requested side
    cannot be found.
    """

    outcome_prices = polymarket_data.get(
        "outcome_prices",
        {},
    )

    normalized = {}

    for key, value in outcome_prices.items():

        normalized[
            str(key).strip().upper()
        ] = value

    return normalized.get(
        side.upper()
    )


def print_header():
    """
    Print the paper-live header.
    """

    print()
    print("=" * 70)

    print(
        "POLYMARKET BTC PAPER LIVE SIGNAL ENGINE"
    )

    print("=" * 70)

    print(
        "PAPER ONLY"
    )

    print(
        "PUBLIC MARKET DATA ONLY"
    )

    print(
        "NO API KEYS"
    )

    print(
        "NO WALLET"
    )

    print(
        "NO REAL ORDERS"
    )

    print(
        "NO REAL TRADING"
    )

    print("=" * 70)


# ============================================================
# SINGLE LIVE CHECK
# ============================================================

def run_once():
    """
    Perform one complete live paper evaluation.

    No trade is executed.
    """

    print()
    print(
        f"UTC: {utc_now()}"
    )

    # --------------------------------------------------------
    # COINBASE
    # --------------------------------------------------------

    print()
    print(
        "Loading Coinbase BTC market data..."
    )

    coinbase = get_coinbase_data()

    # --------------------------------------------------------
    # DATA QUALITY CHECK
    # --------------------------------------------------------
    #
    # market_data.py has a fallback which uses the current
    # BTC ticker price as the temporary opening price when
    # the Coinbase 5-minute candle cannot be retrieved.
    #
    # That fallback is useful for diagnostics, but must NOT
    # be used for paper signal generation.
    #
    # Therefore:
    #
    # REAL 5m CANDLE  -> continue
    # FALLBACK         -> NO SIGNAL
    #

    if coinbase.get(
        "source"
    ) != "Coinbase 5m candle":

        print()
        print("=" * 70)

        print(
            "PAPER SIGNAL"
        )

        print("=" * 70)

        print(
            "NO TRADE"
        )

        print(
            "Reason: Coinbase 5m candle unavailable."
        )

        print(
            f"Data source: "
            f"{coinbase.get('source')}"
        )

        print(
            "Waiting for valid Coinbase 5m candle..."
        )

        print("=" * 70)

        return None

    # --------------------------------------------------------
    # VALID COINBASE DATA
    # --------------------------------------------------------

    print(
        f"BTC 5m Open:       "
        f"${coinbase['btc_open']:,.2f}"
    )

    print(
        f"BTC Current:       "
        f"${coinbase['btc_current']:,.2f}"
    )

    print(
        f"BTC Movement:      "
        f"{coinbase['movement_percent']:+.4f}%"
    )

    print(
        f"Seconds remaining: "
        f"{coinbase['seconds_remaining']}"
    )

    print(
        f"Data source:       "
        f"{coinbase['source']}"
    )

    # --------------------------------------------------------
    # POLYMARKET
    # --------------------------------------------------------

    print()
    print(
        "Loading Polymarket BTC 5-minute market..."
    )

    polymarket = get_polymarket_data()

    print()
    print(
        f"Market: "
        f"{polymarket.get('market_slug')}"
    )

    print(
        f"Question: "
        f"{polymarket.get('question')}"
    )

    print(
        f"Seconds remaining: "
        f"{polymarket.get('seconds_remaining')}"
    )

    # --------------------------------------------------------
    # POLYMARKET PRICES
    # --------------------------------------------------------

    outcome_prices = polymarket.get(
        "outcome_prices",
        {},
    )

    print()
    print(
        "POLYMARKET PRICES"
    )

    print("-" * 70)

    for outcome, price in outcome_prices.items():

        try:

            print(
                f"{outcome:<10} "
                f"{price:.4f} "
                f"({price * 100:.2f}%)"
            )

        except (
            TypeError,
            ValueError,
        ):

            print(
                f"{outcome:<10} "
                "price unavailable"
            )

    # --------------------------------------------------------
    # SYNCHRONIZED REMAINING TIME
    # --------------------------------------------------------
    #
    # Use the smaller value so that we never evaluate
    # a market beyond the time remaining reported by
    # either data source.
    #

    seconds_remaining = min(
        coinbase[
            "seconds_remaining"
        ],

        polymarket[
            "seconds_remaining"
        ],
    )

    # --------------------------------------------------------
    # DETERMINE EXPECTED SIDE
    # --------------------------------------------------------
    #
    # This mirrors the direction logic in strategy.py.
    #
    # Positive BTC movement -> UP
    # Negative BTC movement -> DOWN
    #
    # The actual signal decision remains inside
    # strategy.evaluate().
    #

    movement = coinbase[
        "movement_percent"
    ]

    if movement > 0:

        expected_side = "UP"

    elif movement < 0:

        expected_side = "DOWN"

    else:

        expected_side = "NONE"

    # --------------------------------------------------------
    # EXACT ZERO MOVEMENT
    # --------------------------------------------------------

    if expected_side == "NONE":

        print()
        print("=" * 70)

        print(
            "PAPER SIGNAL"
        )

        print("=" * 70)

        print(
            "NO TRADE"
        )

        print(
            "Reason: BTC movement is exactly zero."
        )

        print("=" * 70)

        return None

    # --------------------------------------------------------
    # GET CORRECT POLYMARKET PRICE
    # --------------------------------------------------------

    market_price = get_market_price(
        polymarket,
        expected_side,
    )

    if market_price is None:

        print()
        print("=" * 70)

        print(
            "PAPER SIGNAL ERROR"
        )

        print("=" * 70)

        print(
            f"Missing Polymarket price for "
            f"{expected_side}."
        )

        print(
            "NO TRADE"
        )

        print("=" * 70)

        return None

    # --------------------------------------------------------
    # STRATEGY EVALUATION
    # --------------------------------------------------------

    result = evaluate(
        btc_open=coinbase[
            "btc_open"
        ],

        btc_current=coinbase[
            "btc_current"
        ],

        seconds_remaining=seconds_remaining,

        market_price=market_price,

        bankroll=PAPER_BANKROLL,

        volatility=DAILY_VOLATILITY,
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print()
    print("=" * 70)

    print(
        "PAPER SIGNAL RESULT"
    )

    print("=" * 70)

    print(
        f"BTC Movement:      "
        f"{movement:+.4f}%"
    )

    print(
        f"Strategy Side:     "
        f"{result.side}"
    )

    print(
        f"Market Price:      "
        f"{result.market_price:.4f}"
    )

    print(
        f"Probability:       "
        f"{result.probability:.2%}"
    )

    print(
        f"Edge:              "
        f"{result.edge:.2%}"
    )

    print(
        f"Kelly:             "
        f"{result.kelly_fraction:.4%}"
    )

    print(
        f"Position:          "
        f"${result.position_size:.2f}"
    )

    print(
        f"Signal:            "
        f"{'YES' if result.signal else 'NO'}"
    )

    print(
        f"Reason:            "
        f"{result.reason}"
    )

    print("=" * 70)

    print(
        "PAPER ONLY - NO TRADE EXECUTED"
    )

    print("=" * 70)

    return result


# ============================================================
# CONTINUOUS PAPER LIVE LOOP
# ============================================================

def run_live():
    """
    Continuously monitor the current BTC 5-minute market.

    This function NEVER places orders.
    """

    print_header()

    print()
    print(
        "Starting PAPER LIVE monitoring..."
    )

    print(
        f"Refresh interval: "
        f"{LOOP_INTERVAL_SECONDS}s"
    )

    print()

    while True:

        try:

            run_once()

        except KeyboardInterrupt:

            print()
            print("=" * 70)

            print(
                "PAPER LIVE STOPPED"
            )

            print(
                "No real trading was performed."
            )

            print("=" * 70)

            return 0

        except Exception as exc:

            print()
            print("=" * 70)

            print(
                "PAPER LIVE ERROR"
            )

            print("=" * 70)

            print(
                f"{type(exc).__name__}: {exc}"
            )

            print()
            print(
                "Waiting before retry..."
            )

            print("=" * 70)

        time.sleep(
            LOOP_INTERVAL_SECONDS
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        raise SystemExit(
            run_live()
        )

    except Exception as exc:

        print()
        print("=" * 70)

        print(
            "FATAL PAPER LIVE ERROR"
        )

        print("=" * 70)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()

        print(
            "NO REAL TRADING WAS PERFORMED."
        )

        raise SystemExit(1)
