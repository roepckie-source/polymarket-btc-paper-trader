"""
Polymarket BTC Paper Live Trader

PAPER ONLY

- Public market data
- No API keys
- No wallet
- No private keys
- No real orders
- No real trading
"""

from datetime import datetime, timezone

from market_data import get_market_data as get_coinbase_data
from polymarket_data import get_market_data as get_polymarket_data
from strategy import evaluate


# ==========================================================
# PAPER CONFIGURATION
# ==========================================================

PAPER_BANKROLL = 100.00
DAILY_VOLATILITY = 0.04


# ==========================================================
# TIME
# ==========================================================

def utc_now():
    return datetime.now(timezone.utc)


# ==========================================================
# POLYMARKET PRICE
# ==========================================================

def get_market_price(polymarket_data, side):
    """
    Return the current Polymarket price for UP or DOWN.
    """

    outcome_prices = polymarket_data.get(
        "outcome_prices",
        {}
    )

    if not isinstance(outcome_prices, dict):
        return None

    return outcome_prices.get(
        side.upper()
    )


# ==========================================================
# HEADER
# ==========================================================

def print_header():

    print()
    print("=" * 60)
    print("POLYMARKET BTC PAPER LIVE TRADER")
    print("=" * 60)
    print("PAPER ONLY")
    print("NO API KEYS")
    print("NO WALLET")
    print("NO PRIVATE KEYS")
    print("NO REAL ORDERS")
    print("NO REAL TRADING")
    print("=" * 60)
    print()


# ==========================================================
# ONE PAPER-LIVE RUN
# ==========================================================

def run_once():

    print_header()

    now = utc_now()

    print("Current UTC:")
    print(
        now.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )
    print()


    # ======================================================
    # 1. MARKET DATA
    # ======================================================

    print("=" * 60)
    print("1. BTC MARKET DATA")
    print("=" * 60)

    btc = get_coinbase_data()

    source = btc.get(
        "source",
        ""
    )

    print(
        f"BTC Open:        "
        f"${btc['btc_open']:,.2f}"
    )

    print(
        f"BTC Current:     "
        f"${btc['btc_current']:,.2f}"
    )

    print(
        f"Movement:        "
        f"{btc['movement_percent']:+.4f}%"
    )

    print(
        f"Window Start:    "
        f"{btc['window_start']}"
    )

    print(
        f"Window End:      "
        f"{btc['window_end']}"
    )

    print(
        f"Seconds Left:    "
        f"{btc['seconds_remaining']}"
    )

    print(
        f"Data Source:     "
        f"{source}"
    )

    print()


    # ======================================================
    # DATA QUALITY CHECK
    # ======================================================

    if source != "Kraken 5m candle + Coinbase ticker":

        print("NO TRADE")
        print(
            "Reason: Valid Kraken 5-minute candle "
            "is unavailable."
        )
        print(
            "Paper-live signal requires a real "
            "5-minute candle."
        )
        print()

        return


    # ======================================================
    # 2. POLYMARKET
    # ======================================================

    print("=" * 60)
    print("2. POLYMARKET MARKET DATA")
    print("=" * 60)

    polymarket = get_polymarket_data()

    print(
        f"Event:           "
        f"{polymarket.get('event_title')}"
    )

    print(
        f"Question:        "
        f"{polymarket.get('question')}"
    )

    print(
        f"Market Slug:     "
        f"{polymarket.get('market_slug')}"
    )

    print(
        f"Condition ID:    "
        f"{polymarket.get('condition_id')}"
    )

    print(
        f"Window Start:    "
        f"{polymarket.get('window_start')}"
    )

    print(
        f"Window End:      "
        f"{polymarket.get('window_end')}"
    )

    print(
        f"Seconds Left:    "
        f"{polymarket.get('seconds_remaining')}"
    )

    print()

    outcome_prices = polymarket.get(
        "outcome_prices",
        {}
    )

    print("Polymarket prices:")
    print()

    for outcome, price in outcome_prices.items():

        print(
            f"  {outcome}: "
            f"{float(price):.4f} "
            f"({float(price) * 100:.2f}%)"
        )

    print()


    # ======================================================
    # 3. TIME VALIDATION
    # ======================================================

    coinbase_seconds = btc.get(
        "seconds_remaining"
    )

    polymarket_seconds = polymarket.get(
        "seconds_remaining"
    )

    if coinbase_seconds is None:

        print("NO TRADE")
        print(
            "Reason: Missing BTC seconds remaining."
        )

        return

    if polymarket_seconds is None:

        print("NO TRADE")
        print(
            "Reason: Missing Polymarket seconds remaining."
        )

        return


    seconds_remaining = min(
        float(coinbase_seconds),
        float(polymarket_seconds)
    )


    # ======================================================
    # 4. BTC DIRECTION
    # ======================================================

    movement = float(
        btc["movement_percent"]
    )

    if movement > 0:

        expected_side = "UP"

    elif movement < 0:

        expected_side = "DOWN"

    else:

        print("NO TRADE")
        print(
            "Reason: BTC movement is exactly zero."
        )

        return


    # ======================================================
    # 5. POLYMARKET ENTRY PRICE
    # ======================================================

    market_price = get_market_price(
        polymarket,
        expected_side
    )

    if market_price is None:

        print("NO TRADE")
        print(
            f"Reason: No Polymarket price found "
            f"for {expected_side}."
        )

        return

    market_price = float(
        market_price
    )


    # ======================================================
    # 6. STRATEGY EVALUATION
    # ======================================================

    print("=" * 60)
    print("3. STRATEGY EVALUATION")
    print("=" * 60)

    print(
        f"Expected Side:       "
        f"{expected_side}"
    )

    print(
        f"BTC Movement:        "
        f"{movement:+.4f}%"
    )

    print(
        f"Market Price:        "
        f"{market_price:.4f}"
    )

    print(
        f"Seconds Remaining:   "
        f"{seconds_remaining:.0f}"
    )

    print(
        f"Paper Bankroll:      "
        f"${PAPER_BANKROLL:.2f}"
    )

    print()


    result = evaluate(
        btc_open=float(
            btc["btc_open"]
        ),

        btc_current=float(
            btc["btc_current"]
        ),

        market_price=market_price,

        seconds_remaining=seconds_remaining,

        bankroll=PAPER_BANKROLL,

        daily_volatility=DAILY_VOLATILITY
    )


    # ======================================================
    # 7. RESULT
    # ======================================================

    print("=" * 60)
    print("4. PAPER SIGNAL RESULT")
    print("=" * 60)

    print(
        f"Signal:              "
        f"{result.signal}"
    )

    print(
        f"Side:                "
        f"{result.side}"
    )

    print(
        f"Probability:         "
        f"{result.probability:.2%}"
    )

    print(
        f"Market Price:        "
        f"{result.market_price:.4f}"
    )

    print(
        f"Edge:                "
        f"{result.edge:.2%}"
    )

    print(
        f"Kelly Fraction:      "
        f"{result.kelly_fraction:.2%}"
    )

    print(
        f"Position Size:       "
        f"${result.position_size:.2f}"
    )

    print(
        f"Reason:              "
        f"{result.reason}"
    )

    print()


    # ======================================================
    # 8. PAPER SIGNAL
    # ======================================================

    if result.signal == "YES":

        print("=" * 60)
        print("PAPER TRADE SIGNAL DETECTED")
        print("=" * 60)

        print()

        print(
            f"Side:                "
            f"{result.side}"
        )

        print(
            f"Entry Price:         "
            f"{result.market_price:.4f}"
        )

        print(
            f"Position Size:       "
            f"${result.position_size:.2f}"
        )

        print(
            f"Probability:         "
            f"{result.probability:.2%}"
        )

        print(
            f"Edge:                "
            f"{result.edge:.2%}"
        )

        print()

        print("IMPORTANT:")
        print("This is a PAPER signal only.")
        print("NO ORDER WAS SENT.")
        print("NO WALLET WAS USED.")
        print("NO MONEY WAS USED.")
        print()

    else:

        print("=" * 60)
        print("NO PAPER TRADE")
        print("=" * 60)

        print()

        print(
            f"Reason: "
            f"{result.reason}"
        )

        print()


    # ======================================================
    # 9. SAFETY
    # ======================================================

    print("=" * 60)
    print("SAFETY CHECK")
    print("=" * 60)

    print("PAPER TRADING ONLY")
    print("NO API KEYS")
    print("NO WALLET")
    print("NO PRIVATE KEYS")
    print("NO REAL ORDERS")
    print("NO REAL TRADING")

    print("=" * 60)


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    try:

        run_once()

    except Exception as exc:

        print()
        print("=" * 60)
        print("PAPER LIVE ERROR")
        print("=" * 60)

        print(
            type(exc).__name__
        )

        print(
            str(exc)
        )

        print("=" * 60)

        raise
