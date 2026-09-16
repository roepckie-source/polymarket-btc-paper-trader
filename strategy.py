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

Based on the investigated BTC 5-minute Up/Down strategy:
- minimum BTC movement: 0.06%
- minimum model probability: 80%
- minimum edge: 5 percentage points
- market price: 0.50 - 0.90
- entry window: T-240 to T-10 seconds
- Quarter-Kelly position sizing
"""

from dataclasses import dataclass
from math import erf, exp, log, sqrt


# ============================================================
# CONFIGURATION
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

# Default annualised volatility assumption.
# Can later be replaced by realised BTC volatility.
DEFAULT_VOLATILITY = 0.12


# ============================================================
# DATA STRUCTURES
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
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


# ============================================================
# BROWNIAN MOTION PROBABILITY
# ============================================================

def estimate_probability(
    btc_open: float,
    btc_current: float,
    seconds_remaining: float,
    volatility: float = DEFAULT_VOLATILITY,
) -> tuple[float, str]:
    """
    Estimate the probability that BTC finishes above its
    starting price at the end of the 5-minute market.

    Uses a simplified Brownian-motion model.

    Returns:
        probability, side
    """

    if btc_open <= 0:
        raise ValueError("btc_open must be > 0")

    if btc_current <= 0:
        raise ValueError("btc_current must be > 0")

    if seconds_remaining <= 0:
        return (
            1.0 if btc_current > btc_open else 0.0,
            "UP" if btc_current > btc_open else "DOWN",
        )

    if volatility <= 0:
        raise ValueError("volatility must be > 0")

    # Log-price displacement.
    displacement = log(btc_current / btc_open)

    # Convert remaining time into a fraction of a year.
    seconds_per_year = 365.25 * 24 * 60 * 60
    time_fraction = seconds_remaining / seconds_per_year

    # Standard deviation of the remaining Brownian movement.
    sigma = volatility * sqrt(time_fraction)

    if sigma <= 0:
        return (
            1.0 if displacement > 0 else 0.0,
            "UP" if displacement > 0 else "DOWN",
        )

    # Probability that final log-price is above the opening price.
    z = displacement / sigma

    probability_up = normal_cdf(z)

    if probability_up >= 0.50:
        return probability_up, "UP"

    return 1.0 - probability_up, "DOWN"


# ============================================================
# KELLY CRITERION
# ============================================================

def calculate_kelly(
    probability: float,
    market_price: float,
) -> float:
    """
    Calculate Kelly fraction for a binary contract.

    b = net odds
    q = probability of losing

    Kelly = (b*p - q) / b

    We later multiply this by KELLY_FRACTION
    (Quarter-Kelly).
    """

    if not 0.0 < probability < 1.0:
        return 0.0

    if not 0.0 < market_price < 1.0:
        return 0.0

    b = (1.0 - market_price) / market_price
    q = 1.0 - probability

    if b <= 0:
        return 0.0

    kelly = ((b * probability) - q) / b

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
        kelly_fraction, position_size
    """

    if bankroll <= 0:
        return 0.0, 0.0

    kelly = calculate_kelly(
        probability=probability,
        market_price=market_price,
    )

    quarter_kelly = kelly * KELLY_FRACTION

    position_size = bankroll * quarter_kelly

    position_size = max(MIN_POSITION_USD, position_size)
    position_size = min(MAX_POSITION_USD, position_size)

    # Never allocate more than bankroll.
    position_size = min(position_size, bankroll)

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
    """

    # --------------------------------------------------------
    # Basic validation
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

    btc_move_pct = abs(
        (btc_current - btc_open) / btc_open
    ) * 100.0

    if btc_move_pct < MIN_BTC_MOVE_PCT:
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            f"BTC movement too small: {btc_move_pct:.4f}%",
        )

    # --------------------------------------------------------
    # Entry time window
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
            f"Too early: {seconds_remaining:.1f}s remaining",
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
            f"Too late: {seconds_remaining:.1f}s remaining",
        )

    # --------------------------------------------------------
    # Market price filter
    # --------------------------------------------------------

    if not (
        MIN_MARKET_PRICE
        <= market_price
        <= MAX_MARKET_PRICE
    ):
        return StrategyResult(
            False,
            "NONE",
            0.0,
            market_price,
            0.0,
            0.0,
            0.0,
            f"Market price outside range: {market_price:.4f}",
        )

    # --------------------------------------------------------
    # Model probability
    # --------------------------------------------------------

    probability, side = estimate_probability(
        btc_open=btc_open,
        btc_current=btc_current,
        seconds_remaining=seconds_remaining,
        volatility=volatility,
    )

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
            f"Probability too low: {probability:.2%}",
        )

    # --------------------------------------------------------
    # Edge
    # --------------------------------------------------------

    edge = probability - market_price

    if edge < MIN_EDGE:
        return StrategyResult(
            False,
            side,
            probability,
            market_price,
            edge,
            0.0,
            0.0,
            f"Edge too small: {edge:.2%}",
        )

    # --------------------------------------------------------
    # Quarter-Kelly
    # --------------------------------------------------------

    kelly_fraction, position_size = calculate_position_size(
        bankroll=bankroll,
        probability=probability,
        market_price=market_price,
    )

    if position_size <= 0:
        return StrategyResult(
            False,
            side,
            probability,
            market_price,
            edge,
            kelly_fraction,
            0.0,
            "Position size is zero",
        )

    # --------------------------------------------------------
    # VALID PAPER SIGNAL
    # --------------------------------------------------------

    return StrategyResult(
        True,
        side,
        probability,
        market_price,
        edge,
        kelly_fraction,
        position_size,
        "VALID PAPER SIGNAL",
    )


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("POLYMARKET BTC PAPER STRATEGY")
    print("=" * 60)

    bankroll = 100.00

    # Example only.
    # This does NOT connect to Polymarket or Binance.

    result = evaluate(
        btc_open=100000.0,
        btc_current=100150.0,
        seconds_remaining=120,
        market_price=0.68,
        bankroll=bankroll,
        volatility=DEFAULT_VOLATILITY,
    )

    print()
    print(f"Signal:       {result.signal}")
    print(f"Side:         {result.side}")
    print(f"Probability:  {result.probability:.2%}")
    print(f"Market price: {result.market_price:.4f}")
    print(f"Edge:         {result.edge:.2%}")
    print(f"Kelly:        {result.kelly_fraction:.2%}")
    print(f"Position:     ${result.position_size:.2f}")
    print(f"Reason:       {result.reason}")
    print()
    print("PAPER ONLY - NO REAL ORDERS")
