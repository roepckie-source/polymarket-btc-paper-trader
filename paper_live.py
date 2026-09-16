from datetime import datetime, timezone

from market_data import get_market_data as get_coinbase_data
from polymarket_data import get_market_data as get_polymarket_data
from strategy import evaluate


PAPER_BANKROLL = 100.00
DAILY_VOLATILITY = 0.04


def utc_now():
    return datetime.now(timezone.utc)


def get_market_price(polymarket_data, side):
    """
    Get the current Polymarket price for UP or DOWN.
    """

    outcome_prices = polymarket_data.get("outcome_prices", {})

    if not isinstance(outcome_prices, dict):
        return None

    return outcome_prices.get(side.upper())


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


def run_once():
    print_header()

    now = utc_now()

    print("Current UTC:")
    print(now.strftime("%Y-%m-%d %H:%M:%S UTC"))
    print()

    # ==========================================================
    # COINBASE
    # ==========================================================

    print("=" * 60)
    print("1. COINBASE MARKET DATA")
    print("=" * 60)

    coinbase = get_coinbase_data()

    source = coinbase.get("source", "")

    print(f"BTC Open:        ${coinbase['btc_open']:,.2f}")
    print(f"BTC Current:     ${coinbase['btc_current']:,.2f}")
    print(f"Movement:        {coinbase['movement_percent']:.4f}%")
    print(f"Window Start:    {coinbase['window_start']}")
    print(f"Window End:      {coinbase['window_end']}")
    print(f"Seconds Left:    {coinbase['seconds_remaining']}")
    print(f"Data Source:     {source}")
    print()

    # IMPORTANT:
    # Never create a live paper signal when Coinbase had to use
    # the ticker fallback instead of the real 5-minute candle.

    if source != "Coinbase 5m candle":
        print("NO TRADE")
        print("Reason: Coinbase 5-minute candle is unavailable.")
        print("Ticker fallback is not accepted for paper-live signals.")
        print()
        return

    # ==========================================================
    # POLYMARKET
    # ==========================================================

    print("=" * 60)
    print("2. POLYMARKET MARKET DATA")
    print("=" * 60)

    polymarket = get_polymarket_data()

    print(f"Event:           {polymarket.get('event_title')}")
    print(f"Question:        {polymarket.get('question')}")
    print(f"Market Slug:     {polymarket.get('market_slug')}")
    print(f"Condition ID:    {polymarket.get('condition_id')}")
    print(f"Window Start:    {polymarket.get('window_start')}")
    print(f"Window End:      {polymarket.get('window_end')}")
    print(f"Seconds Left:    {polymarket.get('seconds_remaining')}")
    print()

    outcome_prices = polymarket.get("outcome_prices", {})

    print("Polymarket prices:")

    for outcome, price in outcome_prices.items():
        print(f"  {outcome}: {price:.4f}")

    print()

    # ==========================================================
    # TIME
    # ==========================================================

    coinbase_seconds = coinbase.get("seconds_remaining")
    polymarket_seconds = polymarket.get("seconds_remaining")

    if coinbase_seconds is None or polymarket_seconds is None:
        print("NO TRADE")
        print("Reason: Missing seconds_remaining.")
        return

    seconds_remaining = min(
        float(coinbase_seconds),
        float(polymarket_seconds),
    )

    # ==========================================================
    # EXPECTED DIRECTION
    # ==========================================================

    movement = float(coinbase["movement_percent"])

    if movement > 0:
        expected_side = "UP"
    elif movement < 0:
        expected_side = "DOWN"
    else:
        print("NO TRADE")
        print("Reason: BTC movement is exactly zero.")
        return

    market_price = get_market_price(
        polymarket,
        expected_side,
    )

    if market_price is None:
        print("NO TRADE")
        print(f"Reason: No Polymarket price found for {expected_side}.")
        return

    # ==========================================================
    # STRATEGY
    # ==========================================================

    print("=" * 60)
    print("3. STRATEGY EVALUATION")
    print("=" * 60)

    print(f"Expected Side:       {expected_side}")
    print(f"BTC Movement:        {movement:.4f}%")
    print(f"Market Price:        {market_price:.4f}")
    print(f"Seconds Remaining:   {seconds_remaining:.0f}")
    print(f"Paper Bankroll:      ${PAPER_BANKROLL:.2f}")
    print()

    result = evaluate(
        btc_open=float(coinbase["btc_open"]),
        btc_current=float(coinbase["btc_current"]),
        market_price=float(market_price),
        seconds_remaining=seconds_remaining,
        bankroll=PAPER_BANKROLL,
        daily_volatility=DAILY_VOLATILITY,
    )

    # ==========================================================
    # RESULT
    # ==========================================================

    print("=" * 60)
    print("4. PAPER SIGNAL RESULT")
    print("=" * 60)

    print(f"Signal:              {result.signal}")
    print(f"Side:                {result.side}")
    print(f"Probability:         {result.probability:.2%}")
    print(f"Market Price:        {result.market_price:.4f}")
    print(f"Edge:                {result.edge:.2%}")
    print(f"Kelly Fraction:      {result.kelly_fraction:.2%}")
    print(f"Position Size:       ${result.position_size:.2f}")
    print(f"Reason:              {result.reason}")
    print()

    # ==========================================================
    # PAPER TRADE SIGNAL
    # ==========================================================

    if result.signal == "YES":
        print("=" * 60)
        print("PAPER TRADE SIGNAL DETECTED")
        print("=" * 60)
        print()
        print(f"Side:                {result.side}")
        print(f"Entry Price:         {result.market_price:.4f}")
        print(f"Position Size:       ${result.position_size:.2f}")
        print(f"Probability:         {result.probability:.2%}")
        print(f"Edge:                {result.edge:.2%}")
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
        print(f"Reason: {result.reason}")
        print()

    # ==========================================================
    # SAFETY
    # ==========================================================

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


if __name__ == "__main__":
    try:
        run_once()
    except Exception as exc:
        print()
        print("=" * 60)
        print("PAPER LIVE ERROR")
        print("=" * 60)
        print(type(exc).__name__)
        print(str(exc))
        print("=" * 60)
        raise
