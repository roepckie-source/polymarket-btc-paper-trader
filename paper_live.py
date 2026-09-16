"""
Polymarket BTC 5-Minute PAPER LIVE SIGNAL ENGINE

ONE-SHOT LIVE TEST

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

from datetime import datetime, timezone

from market_data import get_market_data as get_coinbase_data
from polymarket_data import get_market_data as get_polymarket_data
from strategy import evaluate


# ============================================================
# CONFIGURATION
# ============================================================

PAPER_BANKROLL = 100.00

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
        "ONE-SHOT LIVE TEST"
    )

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

    print_header()

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
    # market_data.py can use the current ticker price
    # as a fallback if the 5-minute candle is unavailable.
    #
    # That fallback MUST NOT be used for signal generation.
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
            "A valid 5-minute opening price is required."
        )

        print("=" * 70)

        print()
        print(
            "ONE-SHOT TEST COMPLETE"
        )

        print(
            "NO REAL TRADING WAS PERFORMED."
        )

        return None

    # --------------------------------------------------------
    # VALID COINBASE DATA
    # --------------------------------------------------------

    print()
    print(
        "COINBASE BTC DATA"
    )

    print("-" * 70)

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
        f"Window start:      "
        f"{datetime.fromtimestamp("
        f"coinbase['window_start'], "
        f"tz=timezone.utc"
        f")}"
    )

    print(
        f"Window end:        "
        f"{datetime.fromtimestamp("
        f"coinbase['window_end'], "
        f"tz=timezone.utc"
        f")}"
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
        "POLYMARKET MARKET"
    )

    print("-" * 70)

    print(
        f"Market:            "
        f"{polymarket.get('market_slug')}"
    )

    print(
        f"Question:          "
        f"{polymarket.get('question')}"
    )

    print(
        f"Seconds remaining: "
        f"{polymarket.get('seconds_remaining')}"
    )

    print()
    print(
        "POLYMARKET PRICES"
    )

    print("-" * 70)

    outcome_prices = polymarket.get(
        "outcome_prices",
        {},
    )

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
    # SYNCHRONIZED TIME
    # --------------------------------------------------------
    #
    # Use the smaller remaining time from both sources.
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
    # BTC DIRECTION
    # --------------------------------------------------------

    movement = coinbase[
        "movement_percent"
    ]

    if movement > 0:

        expected_side = "UP"

    elif movement < 0:

        expected_side = "DOWN"

    else:

        expected_side = "NONE"

    print()
    print(
        f"BTC Direction:    "
        f"{expected_side}"
    )

    print(
        f"Evaluation time:  "
        f"{seconds_remaining}s remaining"
    )

    # --------------------------------------------------------
    # ZERO MOVEMENT
    # --------------------------------------------------------

    if expected_side == "NONE":

        print()
        print("=" * 70)

        print(
            "PAPER SIGNAL RESULT"
        )

        print("=" * 70)

        print(
            "Signal:            NO"
        )

        print(
            "Reason:            BTC movement is exactly zero."
        )

        print("=" * 70)

        print()
        print(
            "ONE-SHOT TEST COMPLETE"
        )

        print(
            "NO REAL TRADING WAS PERFORMED."
        )

        return None

    # --------------------------------------------------------
    # CORRECT POLYMARKET PRICE
    # --------------------------------------------------------

    market_price = get_market_price(
        polymarket,
        expected_side,
    )

    if market_price is None:

        print()
        print("=" * 70)

        print(
            "PAPER SIGNAL RESULT"
        )

        print("=" * 70)

        print(
            "Signal:            NO"
        )

        print(
            f"Reason:            "
            f"Polymarket {expected_side} price unavailable."
        )

        print("=" * 70)

        print()
        print(
            "ONE-SHOT TEST COMPLETE"
        )

        print(
            "NO REAL TRADING WAS PERFORMED."
        )

        return None

    # --------------------------------------------------------
    # STRATEGY
    # --------------------------------------------------------

    print()
    print(
        "Running strategy evaluation..."
    )

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
    # FINAL RESULT
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
        f"Kelly:              "
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

    # --------------------------------------------------------
    # IMPORTANT SAFETY MESSAGE
    # --------------------------------------------------------

    if result.signal:

        print()
        print(
            "PAPER TRADE SIGNAL DETECTED"
        )

        print(
            f"Side:              {result.side}"
        )

        print(
            f"Paper position:    "
            f"${result.position_size:.2f}"
        )

        print(
            "IMPORTANT:"
        )

        print(
            "This is ONLY a paper signal."
        )

        print(
            "NO ORDER WAS PLACED."
        )

    else:

        print()
        print(
            "NO PAPER TRADE SIGNAL"
        )

    print()
    print("=" * 70)

    print(
        "ONE-SHOT TEST COMPLETE"
    )

    print(
        "NO REAL TRADING WAS PERFORMED."
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

    print("=" * 70)

    return result


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        run_once()

    except KeyboardInterrupt:

        print()
        print("=" * 70)

        print(
            "PAPER LIVE TEST INTERRUPTED"
        )

        print(
            "NO REAL TRADING WAS PERFORMED."
        )

        print("=" * 70)

        raise SystemExit(0)

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
            "NO REAL TRADING WAS PERFORMED."
        )

        print("=" * 70)

        raise SystemExit(1)
