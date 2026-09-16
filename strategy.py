"""
Polymarket BTC 5-Minute Strategy
================================

Paper-trading strategy for BTC 5-minute Up/Down markets.

IMPORTANT:
This module contains NO exchange connection, NO wallet and
NO real trading functionality.

The probability model is deliberately conservative.
It uses a short-time BTC volatility estimate instead of
an annualized volatility assumption that can become too
aggressive on a 5-minute horizon.
"""

import math
from dataclasses import dataclass


# ============================================================
# STRATEGY PARAMETERS
# ============================================================

MIN_BTC_MOVE_PCT = 0.06

MIN_PROBABILITY = 0.80

MIN_EDGE = 0.05

MIN_MARKET_PRICE = 0.50
MAX_MARKET_PRICE = 0.90

ENTRY_START_SECONDS = 240
ENTRY_END_SECONDS = 10

KELLY_FRACTION = 0.25

MIN_POSITION_USD = 5.00
MAX_POSITION_USD = 25.00

# Approximate BTC volatility expressed as a DAILY
# standard deviation.
#
# This is intentionally conservative for the paper model.
DEFAULT_DAILY_VOLATILITY = 0.04

SECONDS_PER_DAY = 24 * 60 * 60

# Never allow the model to claim certainty.
PROBABILITY_FLOOR = 0.05
PROBABILITY_CEILING = 0.95


# ============================================================
# RESULT OBJECT
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
        1.0 + math.erf(x / math.sqrt(2.0))
    )


# ============================================================
# PROBABILITY MODEL
# ============================================================

def calculate_probability(
    btc_open: float,
    btc_current: float,
    seconds_remaining: int,
    daily_volatility: float = DEFAULT_DAILY_VOLATILITY,
) -> float:
    """
    Estimate probability that BTC finishes above the
    5-minute opening price.

    The model uses:
        current displacement
        remaining time
        daily BTC volatility

    The daily volatility is converted to the remaining
    time interval.

    This is a model estimate, NOT a guarantee.
    """

    if btc_open <= 0:
        raise ValueError("btc_open must be positive")

    if btc_current <= 0:
        raise ValueError("btc_current must be positive")

    if daily_volatility <= 0:
        raise ValueError(
            "daily_volatility must be positive"
        )

    seconds_remaining = max(
        1,
        seconds_remaining,
    )

    # --------------------------------------------------------
    # Log price displacement
    # --------------------------------------------------------

    displacement = math.log(
        btc_current / btc_open
    )

    # --------------------------------------------------------
    # Convert daily volatility to remaining-time volatility
    # --------------------------------------------------------

    time_fraction_of_day = (
        seconds_remaining
        / SECONDS_PER_DAY
    )

    sigma = (
        daily_volatility
        * math.sqrt(time_fraction_of_day)
    )

    if sigma <= 0:
        return 0.50

    # --------------------------------------------------------
    # Standardized displacement
    # --------------------------------------------------------

    z = displacement / sigma

    probability_up = normal_cdf(z)

    # --------------------------------------------------------
    # Safety bounds
    # --------------------------------------------------------

    probability_up = max(
        PROBABILITY_FLOOR,
        min(
            PROBABILITY_CEILING,
            probability_up,
        ),
    )

    return probability_up


# ============================================================
# KELLY
# ============================================================

def calculate_kelly(
    probability: float,
    market_price: float,
) -> float:
    """
    Calculate the Kelly fraction for a binary contract.
    """

    if market_price <= 0:
        return 0.0

    if market_price >= 1:
        return 0.0

    probability = max(
        0.0,
        min(
            1.0 - 1e-9,
            probability,
        ),
    )

    q = 1.0 - probability

    b = (
        (1.0 - market_price)
        / market_price
    )

    if b <= 0:
        return 0.0

    kelly = (
        probability * b - q
    ) / b

    return max(
        0.0,
        min(
            1.0,
            kelly,
        ),
    )


# ============================================================
# POSITION SIZE
# ============================================================

def calculate_position_size(
    bankroll: float,
    kelly_fraction: float,
) -> float:
    """
    Apply Quarter-Kelly and position limits.
    """

    if bankroll <= 0:
        return 0.0

    if kelly_fraction <= 0:
        return 0.0

    fractional_kelly = (
        kelly_fraction
        * KELLY_FRACTION
    )

    position = (
        bankroll
        * fractional_kelly
    )

    position = min(
        position,
        MAX_POSITION_USD,
        bankroll,
    )

    if position < MIN_POSITION_USD:
        return 0.0

    return position


# ============================================================
# STRATEGY EVALUATION
# ============================================================

def evaluate(
    btc_open: float,
    btc_current: float,
    seconds_remaining: int,
    market_price: float,
    bankroll: float = 100.0,
    daily_volatility: float = DEFAULT_DAILY_VOLATILITY,
) -> StrategyResult:
    """
    Evaluate a BTC 5-minute Up/Down market.
    """

    # --------------------------------------------------------
    # Validate prices
    # --------------------------------------------------------

    if btc_open <= 0:
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            "Invalid BTC opening price",
        )

    if btc_current <= 0:
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            "Invalid BTC current price",
        )

    # --------------------------------------------------------
    # BTC movement
    # --------------------------------------------------------

    move_pct = (
        (btc_current - btc_open)
        / btc_open
        * 100.0
    )

    if abs(move_pct) < MIN_BTC_MOVE_PCT:
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            (
                "BTC movement too small: "
                f"{move_pct:.4f}%"
            ),
        )

    # --------------------------------------------------------
    # Entry window
    # --------------------------------------------------------

    if seconds_remaining > ENTRY_START_SECONDS:
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            (
                "Too early: "
                f"{seconds_remaining}s remaining"
            ),
        )

    if seconds_remaining < ENTRY_END_SECONDS:
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            (
                "Too late: "
                f"{seconds_remaining}s remaining"
            ),
        )

    # --------------------------------------------------------
    # Market price
    # --------------------------------------------------------

    if (
        market_price < MIN_MARKET_PRICE
        or market_price > MAX_MARKET_PRICE
    ):
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            (
                "Market price outside range: "
                f"{market_price:.4f}"
            ),
        )

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    side = (
        "UP"
        if move_pct > 0
        else "DOWN"
    )

    # --------------------------------------------------------
    # Probability
    # --------------------------------------------------------

    probability_up = calculate_probability(
        btc_open=btc_open,
        btc_current=btc_current,
        seconds_remaining=seconds_remaining,
        daily_volatility=daily_volatility,
    )

    if side == "UP":
        probability = probability_up
    else:
        probability = 1.0 - probability_up

    # --------------------------------------------------------
    # Probability filter
    # --------------------------------------------------------

    if probability < MIN_PROBABILITY:
        return StrategyResult(
            False,
            side,
            probability,
            market_price,
            0.0,
            0.0,
            0.0,
            (
                "Probability too low: "
                f"{probability:.2%}"
            ),
        )

    # --------------------------------------------------------
    # Edge
    # --------------------------------------------------------

    edge = (
        probability
        - market_price
    )

    if edge < MIN_EDGE:
        return StrategyResult(
            False,
            side,
            probability,
            market_price,
            edge,
            0.0,
            0.0,
            (
                "Edge too small: "
                f"{edge:.2%}"
            ),
        )

    # --------------------------------------------------------
    # Kelly
    # --------------------------------------------------------

    kelly = calculate_kelly(
        probability,
        market_price,
    )

    if kelly <= 0:
        return StrategyResult(
            False,
            side,
            probability,
            market_price,
            edge,
            kelly,
            0.0,
            "Kelly fraction is zero",
        )

    # --------------------------------------------------------
    # Position size
    # --------------------------------------------------------

    position_size = calculate_position_size(
        bankroll,
        kelly,
    )

    if position_size <= 0:
        return StrategyResult(
            False,
            side,
            probability,
            market_price,
            edge,
            kelly,
            0.0,
            "Position size below minimum",
        )

    # --------------------------------------------------------
    # Valid signal
    # --------------------------------------------------------

    return StrategyResult(
        True,
        side,
        probability,
        market_price,
        edge,
        kelly,
        position_size,
        "Valid signal",
    )


# ============================================================
# SELF TEST
# ============================================================

def run_self_test() -> None:
    """
    Software tests only.

    These tests do NOT demonstrate trading performance.
    """

    print("=" * 60)
    print("POLYMARKET BTC STRATEGY SELF TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Test 1: moderate probability
    # --------------------------------------------------------

    probability = calculate_probability(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        daily_volatility=0.04,
    )

    assert (
        PROBABILITY_FLOOR
        <= probability
        <= PROBABILITY_CEILING
    )

    print(
        f"PASS: probability bounded "
        f"({probability:.2%})"
    )

    # --------------------------------------------------------
    # Test 2: positive Kelly
    # --------------------------------------------------------

    kelly = calculate_kelly(
        probability=0.85,
        market_price=0.68,
    )

    assert kelly > 0

    print(
        f"PASS: positive Kelly "
        f"({kelly:.4%})"
    )

    # --------------------------------------------------------
    # Test 3: insufficient edge
    # --------------------------------------------------------

    result = evaluate(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        market_price=0.90,
        bankroll=100.0,
    )

    assert result.signal is False

    print(
        "PASS: insufficient edge rejected"
    )

    # --------------------------------------------------------
    # Test 4: small movement
    # --------------------------------------------------------

    result = evaluate(
        btc_open=100000.0,
        btc_current=100010.0,
        seconds_remaining=120,
        market_price=0.68,
        bankroll=100.0,
    )

    assert result.signal is False

    print(
        "PASS: small BTC movement rejected"
    )

    # --------------------------------------------------------
    # Test 5: zero Kelly
    # --------------------------------------------------------

    position = calculate_position_size(
        bankroll=100.0,
        kelly_fraction=0.0,
    )

    assert position == 0.0

    print(
        "PASS: zero Kelly produces zero position"
    )

    # --------------------------------------------------------
    # Test 6: Quarter-Kelly sizing
    # --------------------------------------------------------

    position = calculate_position_size(
        bankroll=100.0,
        kelly_fraction=0.20,
    )

    assert position == 5.0

    print(
        f"PASS: Quarter-Kelly sizing "
        f"(${position:.2f})"
    )

    # --------------------------------------------------------
    # Test 7: real-world-style small movement
    # --------------------------------------------------------

    probability = calculate_probability(
        btc_open=75739.08,
        btc_current=75766.20,
        seconds_remaining=204,
        daily_volatility=0.04,
    )

    print()
    print("REALISTIC MARKET EXAMPLE")
    print(
        "BTC movement: +0.0358%"
    )
    print(
        f"Estimated UP probability: "
        f"{probability:.2%}"
    )

    # A small move should NOT automatically produce
    # an extreme probability.
    assert probability < 0.80

    print(
        "PASS: small real-world-style move "
        "does not create an automatic signal"
    )

    print()
    print("=" * 60)
    print("ALL STRATEGY SELF TESTS PASSED")
    print("=" * 60)
    print("SOFTWARE TEST ONLY")
    print("NO PERFORMANCE CLAIM")
    print("NO REAL TRADING")
    print("=" * 60)


if __name__ == "__main__":
    run_self_test()
