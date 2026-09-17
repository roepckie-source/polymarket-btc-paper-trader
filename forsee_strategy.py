"""
FORSEE BTC 5-MINUTE PAPER STRATEGY

PAPER ONLY
NO ORDERS
NO BETS
NO WALLET
NO LIVE TRADING

This version uses an independent probability model.

IMPORTANT:
The Forsee published probability is NOT used as our prediction.

Our probability is calculated from:
    BTC movement
    remaining time
    assumed BTC volatility

The Forsee odds are used only as the market price.

Forsee documentation:
- BTC 5m outcome uses final 60-second TWAP
- oddsUp / oddsDown are live market quotes
- 2% platform fee is applied to winnings
"""

import math
from dataclasses import dataclass

from forsee_prediction_data import get_market_data


# ============================================================
# CONFIGURATION
# ============================================================

# Minimum absolute BTC movement required.
MIN_BTC_MOVE_PCT = 0.06

# Minimum independent model probability.
MIN_PROBABILITY = 0.80

# Minimum net edge after Forsee fee.
MIN_EDGE = 0.05

# Quarter Kelly.
KELLY_FRACTION = 0.25

# Paper bankroll.
DEFAULT_BANKROLL = 100.00

# Position limits.
MIN_POSITION_USD = 5.00
MAX_POSITION_USD = 25.00

# Never enter this close to settlement.
MIN_SECONDS_REMAINING = 10.0

# Forsee fee on winnings.
FORSEE_WINNING_FEE = 0.02

# Assumed BTC daily volatility.
#
# This is a PAPER-MODEL assumption.
# It must later be calibrated against historical data.
DEFAULT_DAILY_VOLATILITY = 0.04

# Final TWAP period for Forsee BTC 5m.
FINAL_TWAP_SECONDS = 60.0


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

    model_probability: float
    forsee_probability: float
    break_even_probability: float

    edge: float

    gross_kelly: float
    quarter_kelly: float

    position_size: float

    seconds_remaining: float
    seconds_to_cutoff: float

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


def normal_cdf(z):
    """
    Standard normal cumulative distribution function.
    """

    return 0.5 * (
        1.0
        + math.erf(
            z / math.sqrt(2.0)
        )
    )


# ============================================================
# INDEPENDENT BTC PROBABILITY MODEL
# ============================================================

def calculate_model_probability(
    movement_pct,
    seconds_remaining,
    daily_volatility=DEFAULT_DAILY_VOLATILITY,
):
    """
    Estimate probability that the final Forsee TWAP
    finishes on the current side of the round open.

    Model assumptions:

    1. Current BTC price is the current state.
    2. Future price changes are approximately normally
       distributed.
    3. Volatility scales with square root of time.
    4. Final 60-second TWAP is the settlement reference.
    5. No directional drift is assumed.

    This is a transparent baseline model.
    It is NOT yet historically calibrated.

    Returns:
        Probability between 0 and 1.
    """

    movement_pct = safe_float(
        movement_pct
    )

    seconds_remaining = safe_float(
        seconds_remaining
    )

    daily_volatility = safe_float(
        daily_volatility
    )

    if daily_volatility <= 0:
        return 0.50

    if seconds_remaining <= 0:
        return (
            1.0
            if movement_pct > 0
            else 0.0
            if movement_pct < 0
            else 0.50
        )

    # --------------------------------------------------------
    # Effective uncertainty period
    #
    # Forsee BTC 5m settles using the final 60-second TWAP.
    #
    # We therefore use the time until the beginning of
    # that final TWAP as the main uncertainty period.
    # --------------------------------------------------------

    effective_seconds = max(
        seconds_remaining
        - FINAL_TWAP_SECONDS,
        1.0,
    )

    # --------------------------------------------------------
    # Volatility scales with sqrt(time).
    #
    # daily_volatility is e.g. 0.04 = 4%.
    # One day = 86,400 seconds.
    # --------------------------------------------------------

    sigma = (
        daily_volatility
        * math.sqrt(
            effective_seconds
            / 86400.0
        )
    )

    if sigma <= 0:
        return (
            1.0
            if movement_pct > 0
            else 0.0
        )

    # Convert percent movement into decimal.
    movement_decimal = (
        movement_pct / 100.0
    )

    # --------------------------------------------------------
    # Z score.
    #
    # Example:
    #
    # current price is above open:
    #
    #     movement > 0
    #
    # probability of finishing above open:
    #
    #     Phi(movement / sigma)
    # --------------------------------------------------------

    z = (
        movement_decimal
        / sigma
    )

    probability_up = normal_cdf(z)

    probability_up = min(
        max(
            probability_up,
            0.0001,
        ),
        0.9999,
    )

    return probability_up


# ============================================================
# FORSEE BREAK-EVEN PROBABILITY
# ============================================================

def calculate_break_even_probability(
    odds,
):
    """
    Calculate the probability required to break even
    after Forsee's 2% fee on winnings.

    Decimal odds:

        odds = 1.50

    Gross profit on $1:

        0.50

    After 2% winnings fee:

        0.50 * 0.98

    Net break-even probability:

        1 / (1 + net_profit)
    """

    odds = safe_float(odds)

    if odds <= 1.0:
        return 1.0

    gross_profit = odds - 1.0

    net_profit = (
        gross_profit
        * (1.0 - FORSEE_WINNING_FEE)
    )

    if net_profit <= 0:
        return 1.0

    return 1.0 / (
        1.0 + net_profit
    )


# ============================================================
# NET KELLY
# ============================================================

def calculate_kelly(
    probability,
    odds,
):
    """
    Calculate Kelly using the net payout after
    Forsee's 2% winning fee.

    b = net profit per $1 stake

    Kelly:

        (b*p - q) / b
    """

    probability = safe_float(
        probability
    )

    odds = safe_float(
        odds
    )

    if odds <= 1.0:
        return 0.0

    if probability <= 0.0:
        return 0.0

    if probability >= 1.0:
        probability = 0.999999

    gross_profit = odds - 1.0

    net_profit = (
        gross_profit
        * (1.0 - FORSEE_WINNING_FEE)
    )

    if net_profit <= 0:
        return 0.0

    q = 1.0 - probability

    kelly = (
        (
            net_profit
            * probability
        )
        - q
    ) / net_profit

    return max(
        0.0,
        kelly,
    )


# ============================================================
# POSITION SIZE
# ============================================================

def calculate_position_size(
    bankroll,
    kelly,
):
    """
    Apply quarter-Kelly and position limits.
    """

    bankroll = safe_float(
        bankroll
    )

    kelly = max(
        0.0,
        kelly,
    )

    quarter_kelly = (
        kelly
        * KELLY_FRACTION
    )

    position = (
        bankroll
        * quarter_kelly
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

    PAPER ONLY.
    No order is placed.
    """

    btc_open = safe_float(
        market_data.get(
            "btc_open"
        )
    )

    btc_current = safe_float(
        market_data.get(
            "btc_current"
        )
    )

    seconds_remaining = safe_float(
        market_data.get(
            "time_remaining"
        )
    )

    seconds_to_cutoff = safe_float(
        market_data.get(
            "time_to_order_cutoff"
        )
    )

    accepting_orders = bool(
        market_data.get(
            "accepting_orders",
            False,
        )
    )

    odds_up = safe_float(
        market_data.get(
            "odds_up"
        )
    )

    odds_down = safe_float(
        market_data.get(
            "odds_down"
        )
    )

    forsee_probability_up = (
        safe_float(
            market_data.get(
                "percent_up"
            )
        )
        / 100.0
    )

    forsee_probability_down = (
        safe_float(
            market_data.get(
                "percent_down"
            )
        )
        / 100.0
    )

    # --------------------------------------------------------
    # BTC MOVEMENT
    # --------------------------------------------------------

    movement = calculate_btc_movement(
        btc_open,
        btc_current,
    )

    # --------------------------------------------------------
    # DATA VALIDATION
    # --------------------------------------------------------

    if btc_open <= 0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=0.0,
            model_probability=0.0,
            forsee_probability=0.0,
            break_even_probability=1.0,
            edge=0.0,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
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
            model_probability=0.0,
            forsee_probability=0.0,
            break_even_probability=1.0,
            edge=0.0,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason=(
                "Too late: "
                f"{seconds_remaining:.1f} seconds remaining"
            ),
        )

    # --------------------------------------------------------
    # CUTOFF CHECK
    # --------------------------------------------------------

    if seconds_to_cutoff <= 0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=0.0,
            model_probability=0.0,
            forsee_probability=0.0,
            break_even_probability=1.0,
            edge=0.0,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason="Forsee order cutoff has passed",
        )

    # --------------------------------------------------------
    # ORDER STATUS
    # --------------------------------------------------------

    if not accepting_orders:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=0.0,
            model_probability=0.0,
            forsee_probability=0.0,
            break_even_probability=1.0,
            edge=0.0,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
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
            model_probability=0.0,
            forsee_probability=0.0,
            break_even_probability=1.0,
            edge=0.0,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason=(
                "BTC movement too small: "
                f"{movement:+.4f}%"
            ),
        )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    if movement > 0:

        side = "UP"

        odds = odds_up

        forsee_probability = (
            forsee_probability_up
        )

    else:

        side = "DOWN"

        odds = odds_down

        forsee_probability = (
            forsee_probability_down
        )

    # --------------------------------------------------------
    # ODDS CHECK
    # --------------------------------------------------------

    if odds <= 1.0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            model_probability=0.0,
            forsee_probability=forsee_probability,
            break_even_probability=1.0,
            edge=0.0,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason=(
                f"Invalid {side} odds: "
                f"{odds}"
            ),
        )

    # --------------------------------------------------------
    # INDEPENDENT MODEL PROBABILITY
    # --------------------------------------------------------

    if movement > 0:

        model_probability = (
            calculate_model_probability(
                movement_pct=movement,
                seconds_remaining=seconds_remaining,
            )
        )

    else:

        probability_up = (
            calculate_model_probability(
                movement_pct=movement,
                seconds_remaining=seconds_remaining,
            )
        )

        model_probability = (
            1.0
            - probability_up
        )

    # --------------------------------------------------------
    # PROBABILITY CHECK
    # --------------------------------------------------------

    if model_probability < MIN_PROBABILITY:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            model_probability=model_probability,
            forsee_probability=forsee_probability,
            break_even_probability=(
                calculate_break_even_probability(
                    odds
                )
            ),
            edge=0.0,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason=(
                f"{side} model probability too low: "
                f"{model_probability:.2%}"
            ),
        )

    # --------------------------------------------------------
    # BREAK-EVEN PROBABILITY
    # --------------------------------------------------------

    break_even_probability = (
        calculate_break_even_probability(
            odds
        )
    )

    # --------------------------------------------------------
    # EDGE
    # --------------------------------------------------------

    edge = (
        model_probability
        - break_even_probability
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
            model_probability=model_probability,
            forsee_probability=forsee_probability,
            break_even_probability=break_even_probability,
            edge=edge,
            gross_kelly=0.0,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason=(
                f"Edge too small: "
                f"{edge:.2%}"
            ),
        )

    # --------------------------------------------------------
    # KELLY
    # --------------------------------------------------------

    gross_kelly = calculate_kelly(
        probability=model_probability,
        odds=odds,
    )

    if gross_kelly <= 0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            model_probability=model_probability,
            forsee_probability=forsee_probability,
            break_even_probability=break_even_probability,
            edge=edge,
            gross_kelly=gross_kelly,
            quarter_kelly=0.0,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason="Kelly fraction is zero",
        )

    # --------------------------------------------------------
    # QUARTER KELLY
    # --------------------------------------------------------

    quarter_kelly = (
        gross_kelly
        * KELLY_FRACTION
    )

    # --------------------------------------------------------
    # POSITION SIZE
    # --------------------------------------------------------

    position_size = (
        calculate_position_size(
            bankroll=bankroll,
            kelly=gross_kelly,
        )
    )

    if position_size <= 0:

        return ForseeStrategyResult(
            signal=False,
            side="NONE",
            btc_open=btc_open,
            btc_current=btc_current,
            btc_movement_pct=movement,
            odds=odds,
            model_probability=model_probability,
            forsee_probability=forsee_probability,
            break_even_probability=break_even_probability,
            edge=edge,
            gross_kelly=gross_kelly,
            quarter_kelly=quarter_kelly,
            position_size=0.0,
            seconds_remaining=seconds_remaining,
            seconds_to_cutoff=seconds_to_cutoff,
            accepting_orders=accepting_orders,
            reason=(
                "Position below minimum "
                f"${MIN_POSITION_USD:.2f}"
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
        model_probability=model_probability,
        forsee_probability=forsee_probability,
        break_even_probability=break_even_probability,
        edge=edge,
        gross_kelly=gross_kelly,
        quarter_kelly=quarter_kelly,
        position_size=position_size,
        seconds_remaining=seconds_remaining,
        seconds_to_cutoff=seconds_to_cutoff,
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

    # --------------------------------------------------------
    # BTC
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MARKET
    # --------------------------------------------------------

    print()
    print("MARKET")
    print("-" * 60)

    print(
        f"Side:                  "
        f"{result.side}"
    )

    print(
        f"Forsee Odds:           "
        f"{result.odds:.6f}"
    )

    print(
        f"Forsee Probability:    "
        f"{result.forsee_probability:.2%}"
    )

    print(
        f"Model Probability:     "
        f"{result.model_probability:.2%}"
    )

    print(
        f"Break-even Probability:"
        f" {result.break_even_probability:.2%}"
    )

    print(
        f"Net Edge:              "
        f"{result.edge:.2%}"
    )

    # --------------------------------------------------------
    # RISK
    # --------------------------------------------------------

    print()
    print("RISK")
    print("-" * 60)

    print(
        f"Kelly:                 "
        f"{result.gross_kelly:.2%}"
    )

    print(
        f"Quarter Kelly:         "
        f"{result.quarter_kelly:.2%}"
    )

    print(
        f"Paper Position:        "
        f"${result.position_size:.2f}"
    )

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    print()
    print("TIMING")
    print("-" * 60)

    print(
        f"Seconds Remaining:     "
        f"{result.seconds_remaining:.1f}"
    )

    print(
        f"Seconds To Cutoff:     "
        f"{result.seconds_to_cutoff:.1f}"
    )

    print(
        f"Accepting Orders:      "
        f"{result.accepting_orders}"
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    print()
    print("STATUS")
    print("-" * 60)

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
        print(
            "PAPER TRADE SIGNAL GENERATED"
        )
    else:
        print(
            "NO PAPER TRADE SIGNAL"
        )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print(
        "FORSEE BTC 5-MINUTE "
        "PAPER STRATEGY TEST"
    )
    print("=" * 60)
    print()

    print(
        "Loading Forsee market data..."
    )

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
