"""
Polymarket BTC 5-Minute Strategy
================================

Paper-trading strategy based on:
- BTC movement
- remaining time in the 5-minute window
- estimated volatility
- market price
- probability / edge
- fractional Kelly sizing

PAPER TRADING ONLY:
- No API keys
- No wallet
- No real orders
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

# Annualized BTC volatility assumption.
DEFAULT_VOLATILITY = 0.12

# Important:
# Prevent the probability model from becoming unrealistically
# close to 0% or 100%.
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
    volatility: float = DEFAULT_VOLATILITY,
) -> float:
    """
    Estimate the probability that BTC finishes above
    the current 5-minute opening price.

    The model uses:
    - current BTC displacement from the 5m open
    - remaining time
    - annualized volatility

    Probability is deliberately capped to avoid artificial
    100% signals.
    """

    if btc_open <= 0:
        raise ValueError("btc_open must be positive")

    if btc_current <= 0:
        raise ValueError("btc_current must be positive")

    if seconds_remaining < 0:
        seconds_remaining = 0

    if volatility <= 0:
        raise ValueError("volatility must be positive")

    # Current log-price displacement.
    displacement = math.log(
        btc_current / btc_open
    )

    # Convert annualized volatility to volatility over
    # the remaining fraction of a year.
    seconds_per_year = 365.25 * 24 * 60 * 60

    time_fraction = (
        max(seconds_remaining, 1)
        / seconds_per_year
    )

    sigma = volatility * math.sqrt(time_fraction)

    if sigma <= 0:
        return PROBABILITY_CEILING if displacement > 0 else PROBABILITY_FLOOR

    # Probability that the final log-price is above
    # the opening price.
    z = displacement / sigma

    probability_up = normal_cdf(z)

    # Keep the model away from artificial 0% / 100%.
    probability_up = max(
        PROBABILITY_FLOOR,
        min(PROBABILITY_CEILING, probability_up),
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
    Calculate Kelly fraction for a binary contract.

    For a contract priced at p_market:
        b = (1 - market_price) / market_price

    Kelly:
        f = (p * b - q) / b

    The result is clamped to [0, 1].
    """

    if market_price <= 0:
        return 0.0

    if market_price >= 1:
        return 0.0

    probability = max(
        0.0,
        min(1.0 - 1e-9, probability),
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
        min(1.0, kelly),
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
        kelly_fraction * KELLY_FRACTION
    )

    position = (
        bankroll * fractional_kelly
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
    volatility: float = DEFAULT_VOLATILITY,
) -> StrategyResult:
    """
    Evaluate the current BTC 5-minute market.

    Returns a StrategyResult containing either:
    - a valid paper-trading signal
    - or the reason why there is no signal
    """

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

    absolute_move = abs(move_pct)

    if absolute_move < MIN_BTC_MOVE_PCT:

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
    # Market price filter
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

    # For DOWN we mirror the probability.
    probability_up = calculate_probability(
        btc_open=btc_open,
        btc_current=btc_current,
        seconds_remaining=seconds_remaining,
        volatility=volatility,
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
    Internal software tests.

    These tests verify code behaviour only.
    They are NOT performance tests.
    """

    print("=" * 60)
    print("POLYMARKET BTC STRATEGY SELF TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Test 1: probability is bounded
    # --------------------------------------------------------

    probability = calculate_probability(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        volatility=0.12,
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
    # Test 3: negative edge
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
        "PASS: negative/insufficient edge rejected"
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
    # Test 7: valid strategy path
    # --------------------------------------------------------

    result = evaluate(
        btc_open=100000.0,
        btc_current=100200.0,
        seconds_remaining=120,
        market_price=0.60,
        bankroll=100.0,
        volatility=0.12,
    )

    print()
    print("VALID PATH TEST")
    print(
        f"Probability: {result.probability:.2%}"
    )
    print(
        f"Edge:        {result.edge:.2%}"
    )
    print(
        f"Kelly:       {result.kelly_fraction:.4%}"
    )
    print(
        f"Position:    ${result.position_size:.2f}"
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
