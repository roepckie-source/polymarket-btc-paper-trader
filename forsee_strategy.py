"""
FORSEE BTC 5-MINUTE PAPER STRATEGY

PAPER ONLY
NO ORDERS
NO WALLET
NO LIVE TRADING

Purpose:
- Read current Forsee BTC 5-minute market
- Calculate BTC movement
- Determine UP/DOWN direction
- Calculate implied probability from Forsee odds
- Calculate market edge
- Apply minimum movement / probability / edge filters
- Calculate quarter-Kelly position size
- Return a paper signal

IMPORTANT:
This file does NOT place orders.
"""

from dataclasses import dataclass
from typing import Optional

from forsee_prediction_data import get_market_data


# ============================================================
# STRATEGY CONFIGURATION
# ============================================================

# Minimum BTC movement required to consider a trade.
MIN_BTC_MOVE_PCT = 0.06

# Minimum probability required.
MIN_PROBABILITY = 0.80

# Minimum edge required.
MIN_EDGE = 0.05

# Quarter Kelly.
KELLY_FRACTION = 0.25

# Paper bankroll.
DEFAULT_BANKROLL = 100.00

# Minimum and maximum paper position.
MIN_POSITION_USD = 5.00
MAX_POSITION_USD = 25.00

# Never enter if less than this many seconds remain.
MIN_SECONDS_REMAINING = 10.0

# Forsee does not accept orders after cutoff.
# We require accepting_orders == True.
REQUIRE_ACCEPTING_ORDERS = True


# ============================================================
# RESULT
# ============================================================

@dataclass
class ForseeStrategyResult:

    signal: bool
    side: str

    btc_open: float
    btc_current: float
    btc_movement_pct: float

    odds: float
    implied_probability: float

    market_probability: float
    edge: float

    kelly_fraction: float
    position_size: float

    seconds_remaining: float
    accepting_orders: bool

    reason: str


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_btc_movement(
    btc_open,
    btc_current,
):
    """
    Calculate BTC movement in percent.
    """

    btc_open = safe_float(btc_open)
    btc_current = safe_float(btc_current)

    if btc_open <= 0:
        return 0.0

    return (
        (btc_current - btc_open)
        / btc_open
        * 100.0
    )


def calculate_implied_probability(odds):
    """
    Convert decimal odds to implied probability.

    Example:

        odds = 2.00
        probability = 0.50

        odds = 1.25
        probability = 0.80

    """

    odds = safe_float(odds)

    if odds <= 1.0:
        return 0.0

    return 1.0 / odds


def calculate_edge(
    estimated_probability,
    market_probability,
):
    """
    Edge = estimated probability - market probability.
    """

    return (
        estimated_probability
        - market_probability
    )


def calculate_kelly(
    probability,
    odds,
):
    """
    Standard Kelly criterion for decimal odds.

    b = odds - 1

    Kelly =
        (b*p - q) / b

    where:
        p = probability of winning
        q = 1-p

    Result is capped at zero.
    """

    probability = safe_float(probability)
    odds = safe_float(odds)

    if odds <= 1.0:
        return 0.0

    if probability <= 0.0:
        return 0.0

    if probability >= 1.0:
        probability = 0.999999

    b = odds - 1.0
    q = 1.0 - probability

    kelly = (
        (b * probability) - q
    ) / b

    return max(0.0, kelly)


def calculate_position_size(
    bankroll,
    kelly,
):
    """
    Apply quarter-Kelly and position limits.
    """

    bankroll = safe_float(bankroll)

    kelly = max(0.0, kelly)

    position = (
        bankroll
        * kelly
        * KELLY_FRACTION
    )

    if position < MIN_POSITION_USD:
        return 0.0

    position = min(
        position,
        MAX_POSITION_USD,
    )

    return position


# ============================================================
# STRATEGY EVALUATION
# ============================================================

def evaluate(
    market_data,
    bankroll=DEFAULT_BANKROLL,
):
    """
    Evaluate current Forsee market.

    No orders are placed.
    """

    btc_open = safe_float(
        market_data.get("btc_open")
    )

    btc_current = safe_float(
        market_data.get("btc_current")
    )

    seconds_remaining = safe_float(
        market_data.get("time_remaining")
    )

    accepting_orders = bool(
        market_data.get(
            "accepting_orders",
            False,
        )
    )

    odds_up = safe_float(
        market_data.get("odds_up")
    )

    odds_down = safe_float(
        market_data.get("odds_down")
    )

    percent_up = safe_float(
        market_data.get("percent_up")
    )

    percent_down = safe_float(
        market_data.get("percent_down")
    )

    # --------------------------------------------------------
    # BTC MOVEMENT
    # --------------------------------------------------------

    movement = calculate_btc_movement(
        btc_open,
        btc_current,
    )

    # --------------------------------------------------------
    # BASIC DATA CHECK
    # --------------------------------------------------------

    if btc_open <= 0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=0.0,
            implied_probability=0.0,
            market_probability=0.0,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason="Invalid BTC open price",
        )

    # --------------------------------------------------------
    # TIME CHECK
    # --------------------------------------------------------

    if seconds_remaining <= MIN_SECONDS_REMAINING:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=0.0,
            implied_probability=0.0,
            market_probability=0.0,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason=(
                "Too late: "
                f"{seconds_remaining:.1f} seconds remaining"
            ),
        )

    # --------------------------------------------------------
    # ORDER STATUS
    # --------------------------------------------------------

    if (
        REQUIRE_ACCEPTING_ORDERS
        and not accepting_orders
    ):

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=0.0,
            implied_probability=0.0,
            market_probability=0.0,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason="Forsee is not accepting orders",
        )

    # --------------------------------------------------------
    # MOVEMENT CHECK
    # --------------------------------------------------------

    if abs(movement) < MIN_BTC_MOVE_PCT:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=0.0,
            implied_probability=0.0,
            market_probability=0.0,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason=(
                "BTC movement too small: "
                f"{movement:+.4f}%"
            ),
        )

    # --------------------------------------------------------
    # DETERMINE DIRECTION
    # --------------------------------------------------------

    if movement > 0:

        side = "UP"
        odds = odds_up
        market_probability = (
            percent_up / 100.0
        )

    else:

        side = "DOWN"
        odds = odds_down
        market_probability = (
            percent_down / 100.0
        )

    # --------------------------------------------------------
    # ODDS VALIDATION
    # --------------------------------------------------------

    if odds <= 1.0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            implied_probability=0.0,
            market_probability=market_probability,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason=(
                f"Invalid {side} odds: {odds}"
            ),
        )

    # --------------------------------------------------------
    # IMPLIED PROBABILITY
    # --------------------------------------------------------

    implied_probability = (
        calculate_implied_probability(
            odds
        )
    )

    # --------------------------------------------------------
    # PROBABILITY
    # --------------------------------------------------------
    #
    # IMPORTANT:
    #
    # For the first paper implementation we use
    # Forsee's own published probability as the
    # market probability.
    #
    # This is NOT yet our independent BTC prediction.
    #
    # The next strategy version can replace this
    # with an independently calculated probability.
    #

    estimated_probability = (
        market_probability
    )

    # --------------------------------------------------------
    # PROBABILITY CHECK
    # --------------------------------------------------------

    if estimated_probability < MIN_PROBABILITY:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            implied_probability=implied_probability,
            market_probability=market_probability,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason=(
                f"{side} probability too low: "
                f"{estimated_probability:.2%}"
            ),
        )

    # --------------------------------------------------------
    # EDGE
    # --------------------------------------------------------
    #
    # Because we currently use Forsee's own probability,
    # we do NOT invent an independent edge.
    #
    # We therefore compare published probability
    # against implied probability from the odds.
    #

    edge = calculate_edge(
        estimated_probability,
        implied_probability,
    )

    # --------------------------------------------------------
    # EDGE CHECK
    # --------------------------------------------------------

    if edge < MIN_EDGE:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            implied_probability=implied_probability,
            market_probability=market_probability,
            edge=edge,
            kelly_fraction=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason=(
                f"Edge too small: "
                f"{edge:.2%}"
            ),
        )

    # --------------------------------------------------------
    # KELLY
    # --------------------------------------------------------

    kelly = calculate_kelly(
        estimated_probability,
        odds,
    )

    if kelly <= 0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            implied_probability=implied_probability,
            market_probability=market_probability,
            edge=edge,
            kelly_fraction=kelly,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason="Kelly fraction is zero",
        )

    # --------------------------------------------------------
    # POSITION SIZE
    # --------------------------------------------------------

    position_size = calculate_position_size(
        bankroll,
        kelly,
    )

    if position_size <= 0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            implied_probability=implied_probability,
            market_probability=market_probability,
            edge=edge,
            kelly_fraction=kelly,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            accepting_orders=accepting_orders,
            reason=(
                f"Position below minimum ${MIN_POSITION_USD:.2f}"
            ),
        )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    return ForseeStrategyResult(
        signal=True,
        side=side,
        btc_open=btc_open,
        btc_current=btc_current,
        btc_movement_pct=movement,
        odds=odds,
        implied_probability=estimated_probability,
        market_probability=market_probability,
        edge=edge,
        kelly_fraction=kelly,
        position_size=position_size,
        seconds_remaining=seconds_remaining,
        accepting_orders=accepting_orders,
        reason=(
            f"FORSEE PAPER SIGNAL: {side}"
        ),
    )


# ============================================================
# PRINT RESULT
# ============================================================

def print_result(result):

    print()
    print("=" * 60)
    print("FORSEE PAPER STRATEGY")
    print("=" * 60)

    print()
    print("PAPER ONLY")
    print("NO ORDERS")
    print("NO BETS")
    print("NO WALLET")
    print()

    print("BTC")
    print("-" * 60)

    print(
        f"BTC Open:              "
        f"${result.btc_open:,.2f}"
    )

    print(
        f"BTC Current:           "
        f"${result.btc_current:,.2f}"
    )

    print(
        f"BTC Movement:          "
        f"{result.btc_movement_pct:+.4f}%"
    )

    print()
    print("MARKET")
    print("-" * 60)

    print(
        f"Side:                  "
        f"{result.side}"
    )

    print(
        f"Odds:                  "
        f"{result.odds:.6f}"
    )

    print(
        f"Implied Probability:   "
        f"{result.implied_probability:.2%}"
    )

    print(
        f"Market Probability:    "
        f"{result.market_probability:.2%}"
    )

    print(
        f"Edge:                  "
        f"{result.edge:.2%}"
    )

    print()
    print("RISK")
    print("-" * 60)

    print(
        f"Kelly:                 "
        f"{result.kelly_fraction:.2%}"
    )

    print(
        f"Quarter Kelly:         "
        f"{result.kelly_fraction * KELLY_FRACTION:.2%}"
    )

    print(
        f"Paper Position:       "
        f"${result.position_size:.2f}"
    )

    print()
    print("STATUS")
    print("-" * 60)

    print(
        f"Seconds Remaining:     "
        f"{result.seconds_remaining:.1f}"
    )

    print(
        f"Accepting Orders:      "
        f"{result.accepting_orders}"
    )

    print(
        f"Signal:                "
        f"{result.signal}"
    )

    print(
        f"Reason:                "
        f"{result.reason}"
    )

    print()
    print("=" * 60)

    if result.signal:
        print("PAPER TRADE SIGNAL GENERATED")
    else:
        print("NO PAPER TRADE SIGNAL")

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("FORSEE BTC 5-MINUTE PAPER STRATEGY TEST")
    print("=" * 60)
    print()

    print("Loading Forsee market data...")

    market_data = get_market_data()

    result = evaluate(
        market_data,
        bankroll=DEFAULT_BANKROLL,
    )

    print_result(result)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
