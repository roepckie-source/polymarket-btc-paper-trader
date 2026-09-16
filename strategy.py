"""
Polymarket BTC Paper Trader
===========================

Strategy engine only.

IMPORTANT:
- PAPER ONLY
- NO API CONNECTION
- NO REAL ORDERS
- NO PRIVATE KEYS
- NO EXCHANGE ACCESS

This module contains the mathematical strategy only.
It does not connect to Binance or Polymarket.
It cannot execute trades.
"""

from dataclasses import dataclass
from math import erf, log, sqrt


# ============================================================
# CONFIGURATION
# ============================================================

# Minimum absolute BTC movement from the 5-minute opening price.
MIN_BTC_MOVE_PCT = 0.06

# Minimum model probability required.
MIN_PROBABILITY = 0.80

# Minimum difference between model probability
# and Polymarket market price.
MIN_EDGE = 0.05

# Allowed Polymarket contract price.
MIN_MARKET_PRICE = 0.50
MAX_MARKET_PRICE = 0.90

# Entry window.
#
# Trade only between:
# T-240 seconds
# and
# T-10 seconds
ENTRY_START_SECONDS = 240
ENTRY_END_SECONDS = 10

# Quarter Kelly.
KELLY_FRACTION = 0.25

# Position limits.
MIN_POSITION_USD = 5.00
MAX_POSITION_USD = 25.00

# Default annualised volatility assumption.
#
# This is deliberately configurable.
# Later we can replace this with realised BTC volatility.
DEFAULT_VOLATILITY = 0.12


# ============================================================
# RESULT STRUCTURE
# ============================================================

@dataclass
class StrategyResult:
    signal: bool
    side: str
    probability: float
    market_price: float
    edge: float
    kelly_fraction: float
    position_size: float
    reason: str


# ============================================================
# NORMAL DISTRIBUTION
# ============================================================

def normal_cdf(x: float) -> float:
    """
    Standard normal cumulative distribution function.
    """

    return 0.5 * (
        1.0 + erf(x / sqrt(2.0))
    )


# ============================================================
# PROBABILITY ESTIMATION
# ============================================================

def estimate_probability(
    btc_open: float,
    btc_current: float,
    seconds_remaining: float,
    volatility: float = DEFAULT_VOLATILITY,
) -> tuple[float, str]:
    """
    Estimate the probability that BTC finishes above
    or below the 5-minute opening price.

    Uses a simplified Brownian-motion model.

    Returns:
        probability, side
    """

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if btc_open <= 0:
        raise ValueError(
            "btc_open must be greater than zero"
        )

    if btc_current <= 0:
        raise ValueError(
            "btc_current must be greater than zero"
        )

    if volatility <= 0:
        raise ValueError(
            "volatility must be greater than zero"
        )

    # --------------------------------------------------------
    # MARKET ALREADY EXPIRED
    # --------------------------------------------------------

    if seconds_remaining <= 0:

        if btc_current > btc_open:

            return 1.0, "UP"

        if btc_current < btc_open:

            return 1.0, "DOWN"

        # Exactly equal.
        return 0.5, "UP"

    # --------------------------------------------------------
    # LOG PRICE DISPLACEMENT
    # --------------------------------------------------------

    displacement = log(
        btc_current / btc_open
    )

    # --------------------------------------------------------
    # TIME CONVERSION
    # --------------------------------------------------------

    seconds_per_year = (
        365.25
        * 24.0
        * 60.0
        * 60.0
    )

    time_fraction = (
        seconds_remaining
        / seconds_per_year
    )

    # --------------------------------------------------------
    # REMAINING STANDARD DEVIATION
    # --------------------------------------------------------

    sigma = (
        volatility
        * sqrt(time_fraction)
    )

    if sigma <= 0:

        if displacement > 0:

            return 1.0, "UP"

        if displacement < 0:

            return 1.0, "DOWN"

        return 0.5, "UP"

    # --------------------------------------------------------
    # Z-SCORE
    # --------------------------------------------------------

    z = displacement / sigma

    # --------------------------------------------------------
    # PROBABILITY UP
    # --------------------------------------------------------

    probability_up = normal_cdf(z)

    # --------------------------------------------------------
    # SAFETY BOUND
    #
    # Never pass exactly 0% or 100% into the Kelly
    # calculation. A model should never claim absolute
    # certainty.
    # --------------------------------------------------------

    probability_up = min(
        max(probability_up, 1e-9),
        1.0 - 1e-9,
    )

    # --------------------------------------------------------
    # SELECT SIDE
    # --------------------------------------------------------

    if probability_up >= 0.50:

        return probability_up, "UP"

    probability_down = 1.0 - probability_up

    probability_down = min(
        max(probability_down, 1e-9),
        1.0 - 1e-9,
    )

    return probability_down, "DOWN"


# ============================================================
# KELLY CRITERION
# ============================================================

def calculate_kelly(
    probability: float,
    market_price: float,
) -> float:
    """
    Calculate the Kelly fraction for a binary contract.

    p = probability of winning
    q = probability of losing
    b = net odds

    Kelly:

        f = (b*p - q) / b

    Returns zero when the mathematical edge is not positive.

    IMPORTANT:
    Exactly 0% and 100% probabilities are never accepted
    as absolute certainty.
    """

    # --------------------------------------------------------
    # VALIDATE PROBABILITY
    # --------------------------------------------------------

    if probability <= 0.0:

        return 0.0

    if probability >= 1.0:

        probability = 1.0 - 1e-9

    # --------------------------------------------------------
    # VALIDATE MARKET PRICE
    # --------------------------------------------------------

    if market_price <= 0.0:

        return 0.0

    if market_price >= 1.0:

        return 0.0

    # --------------------------------------------------------
    # NET ODDS
    # --------------------------------------------------------

    b = (
        (1.0 - market_price)
        / market_price
    )

    # Probability of losing.
    q = 1.0 - probability

    if b <= 0.0:

        return 0.0

    # --------------------------------------------------------
    # KELLY
    # --------------------------------------------------------

    kelly = (
        (b * probability) - q
    ) / b

    # Never return negative Kelly.
    return max(0.0, kelly)


# ============================================================
# POSITION SIZE
# ============================================================

def calculate_position_size(
    bankroll: float,
    probability: float,
    market_price: float,
) -> tuple[float, float]:
    """
    Calculate Quarter-Kelly position size.

    Returns:

        quarter_kelly_fraction
        position_size_usd

    IMPORTANT:

    If Kelly is zero or negative, position size is zero.

    The minimum $5 position is applied only after a valid
    positive Kelly calculation.
    """

    # --------------------------------------------------------
    # VALIDATE BANKROLL
    # --------------------------------------------------------

    if bankroll <= 0:

        return 0.0, 0.0

    # --------------------------------------------------------
    # FULL KELLY
    # --------------------------------------------------------

    full_kelly = calculate_kelly(
        probability=probability,
        market_price=market_price,
    )

    # --------------------------------------------------------
    # NO POSITIVE EDGE
    # --------------------------------------------------------

    if full_kelly <= 0.0:

        return 0.0, 0.0

    # --------------------------------------------------------
    # QUARTER KELLY
    # --------------------------------------------------------

    quarter_kelly = (
        full_kelly
        * KELLY_FRACTION
    )

    if quarter_kelly <= 0.0:

        return 0.0, 0.0

    # --------------------------------------------------------
    # RAW POSITION
    # --------------------------------------------------------

    position_size = (
        bankroll
        * quarter_kelly
    )

    # --------------------------------------------------------
    # POSITION LIMITS
    # --------------------------------------------------------

    position_size = max(
        MIN_POSITION_USD,
        position_size,
    )

    position_size = min(
        MAX_POSITION_USD,
        position_size,
    )

    # Never use more than the bankroll.
    position_size = min(
        position_size,
        bankroll,
    )

    return quarter_kelly, position_size


# ============================================================
# STRATEGY EVALUATION
# ============================================================

def evaluate(
    btc_open: float,
    btc_current: float,
    seconds_remaining: float,
    market_price: float,
    bankroll: float,
    volatility: float = DEFAULT_VOLATILITY,
) -> StrategyResult:
    """
    Evaluate one Polymarket BTC 5-minute opportunity.

    No trade is executed here.

    This function only produces a mathematical signal.
    """

    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

    if btc_open <= 0:

        return StrategyResult(
            signal=False,
            side="NONE",
            probability=0.0,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason="Invalid BTC opening price",
        )

    if btc_current <= 0:

        return StrategyResult(
            signal=False,
            side="NONE",
            probability=0.0,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason="Invalid BTC current price",
        )

    if market_price <= 0:

        return StrategyResult(
            signal=False,
            side="NONE",
            probability=0.0,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason="Invalid market price",
        )

    # --------------------------------------------------------
    # BTC MOVEMENT
    # --------------------------------------------------------

    btc_move_pct = (
        abs(
            (btc_current - btc_open)
            / btc_open
        )
        * 100.0
    )

    if btc_move_pct < MIN_BTC_MOVE_PCT:

        return StrategyResult(
            signal=False,
            side="NONE",
            probability=0.0,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason=(
                "BTC movement too small: "
                f"{btc_move_pct:.4f}%"
            ),
        )

    # --------------------------------------------------------
    # ENTRY WINDOW
    # --------------------------------------------------------

    if seconds_remaining > ENTRY_START_SECONDS:

        return StrategyResult(
            signal=False,
            side="NONE",
            probability=0.0,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason=(
                "Too early: "
                f"{seconds_remaining:.1f}s remaining"
            ),
        )

    if seconds_remaining < ENTRY_END_SECONDS:

        return StrategyResult(
            signal=False,
            side="NONE",
            probability=0.0,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason=(
                "Too late: "
                f"{seconds_remaining:.1f}s remaining"
            ),
        )

    # --------------------------------------------------------
    # MARKET PRICE RANGE
    # --------------------------------------------------------

    if not (
        MIN_MARKET_PRICE
        <= market_price
        <= MAX_MARKET_PRICE
    ):

        return StrategyResult(
            signal=False,
            side="NONE",
            probability=0.0,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason=(
                "Market price outside range: "
                f"{market_price:.4f}"
            ),
        )

    # --------------------------------------------------------
    # MODEL PROBABILITY
    # --------------------------------------------------------

    probability, side = estimate_probability(
        btc_open=btc_open,
        btc_current=btc_current,
        seconds_remaining=seconds_remaining,
        volatility=volatility,
    )

    # --------------------------------------------------------
    # PROBABILITY FILTER
    # --------------------------------------------------------

    if probability < MIN_PROBABILITY:

        return StrategyResult(
            signal=False,
            side=side,
            probability=probability,
            market_price=market_price,
            edge=0.0,
            kelly_fraction=0.0,
            position_size=0.0,
            reason=(
                "Probability too low: "
                f"{probability:.2%}"
            ),
        )

    # --------------------------------------------------------
    # EDGE
    # --------------------------------------------------------

    edge = (
        probability
        - market_price
    )

    if edge < MIN_EDGE:

        return StrategyResult(
            signal=False,
            side=side,
            probability=probability,
            market_price=market_price,
            edge=edge,
            kelly_fraction=0.0,
            position_size=0.0,
            reason=(
                "Edge too small: "
                f"{edge:.2%}"
            ),
        )

    # --------------------------------------------------------
    # QUARTER KELLY
    # --------------------------------------------------------

    kelly_fraction, position_size = (
        calculate_position_size(
            bankroll=bankroll,
            probability=probability,
            market_price=market_price,
        )
    )

    # --------------------------------------------------------
    # KELLY SAFETY
    # --------------------------------------------------------

    if kelly_fraction <= 0.0:

        return StrategyResult(
            signal=False,
            side=side,
            probability=probability,
            market_price=market_price,
            edge=edge,
            kelly_fraction=0.0,
            position_size=0.0,
            reason="Kelly calculation produced zero",
        )

    if position_size <= 0.0:

        return StrategyResult(
            signal=False,
            side=side,
            probability=probability,
            market_price=market_price,
            edge=edge,
            kelly_fraction=kelly_fraction,
            position_size=0.0,
            reason="Position size is zero",
        )

    # --------------------------------------------------------
    # VALID SIGNAL
    # --------------------------------------------------------

    return StrategyResult(
        signal=True,
        side=side,
        probability=probability,
        market_price=market_price,
        edge=edge,
        kelly_fraction=kelly_fraction,
        position_size=position_size,
        reason="VALID PAPER SIGNAL",
    )


# ============================================================
# STRATEGY SELF TEST
# ============================================================

def run_self_test():

    print()
    print("=" * 60)
    print("STRATEGY ENGINE SELF TEST")
    print("=" * 60)
    print("PAPER ONLY")
    print("NO API")
    print("NO REAL ORDERS")
    print()

    # --------------------------------------------------------
    # TEST 1
    # --------------------------------------------------------

    kelly = calculate_kelly(
        probability=0.90,
        market_price=0.68,
    )

    assert kelly > 0.0

    print("PASS: positive Kelly")

    # --------------------------------------------------------
    # TEST 2
    # --------------------------------------------------------

    kelly_zero = calculate_kelly(
        probability=0.60,
        market_price=0.68,
    )

    assert kelly_zero == 0.0

    print("PASS: negative-edge Kelly rejection")

    # --------------------------------------------------------
    # TEST 3
    # --------------------------------------------------------

    kelly_boundary = calculate_kelly(
        probability=1.0,
        market_price=0.68,
    )

    assert kelly_boundary > 0.0

    print(
        "PASS: 100% probability boundary handling"
    )

    # --------------------------------------------------------
    # TEST 4
    # --------------------------------------------------------

    quarter_kelly, position = (
        calculate_position_size(
            bankroll=100.0,
            probability=0.90,
            market_price=0.68,
        )
    )

    assert quarter_kelly > 0.0
    assert position > 0.0

    print("PASS: Quarter-Kelly position sizing")

    # --------------------------------------------------------
    # TEST 5
    # --------------------------------------------------------

    zero_kelly, zero_position = (
        calculate_position_size(
            bankroll=100.0,
            probability=0.60,
            market_price=0.68,
        )
    )

    assert zero_kelly == 0.0
    assert zero_position == 0.0

    print(
        "PASS: zero-Kelly position rejection"
    )

    # --------------------------------------------------------
    # TEST 6
    # --------------------------------------------------------

    result = evaluate(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        market_price=0.68,
        bankroll=100.0,
        volatility=0.12,
    )

    assert result.signal is True
    assert result.kelly_fraction > 0.0
    assert result.position_size > 0.0

    print("PASS: strategy evaluation")

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("ALL STRATEGY SELF TESTS PASSED")
    print("=" * 60)
    print()
    print("No API connection.")
    print("No wallet.")
    print("No real orders.")
    print("Paper only.")
    print()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    run_self_test()
