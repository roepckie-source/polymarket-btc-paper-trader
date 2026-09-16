"""
Polymarket BTC Paper Trader Test Suite
======================================

Software tests only.

NO:
- API keys
- Wallet
- Real orders
- Live trading
"""

from paper_trader import PaperTrader


# ============================================================
# TEST DATA
# ============================================================

BTC_OPEN = 100000.00
BTC_CURRENT = 100500.00

SECONDS_REMAINING = 120

MARKET_PRICE = 0.68

VOLATILITY = 0.04


# ============================================================
# TEST 1 - WINNING TRADE
# ============================================================

def test_winning_trade():

    print("=" * 60)
    print("TEST 1 - WINNING TRADE")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_winning.csv",
    )

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is True, "Trade should have opened"

    # The strategy opened UP.
    # Simulate UP winning.
    resolved = trader.resolve_trade(
        winning_side="UP"
    )

    assert resolved is True

    assert trader.winning_trades == 1
    assert trader.losing_trades == 0

    print("PASS: winning trade")


# ============================================================
# TEST 2 - LOSING TRADE
# ============================================================

def test_losing_trade():

    print("=" * 60)
    print("TEST 2 - LOSING TRADE")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_losing.csv",
    )

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is True, "Trade should have opened"

    # The strategy opened UP.
    # Simulate DOWN winning -> our UP position loses.
    resolved = trader.resolve_trade(
        winning_side="DOWN"
    )

    assert resolved is True

    assert trader.winning_trades == 0
    assert trader.losing_trades == 1

    print("PASS: losing trade")


# ============================================================
# TEST 3 - NO SIGNAL
# ============================================================

def test_no_signal():

    print("=" * 60)
    print("TEST 3 - NO SIGNAL")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_no_signal.csv",
    )

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_OPEN + 10,
        seconds_remaining=120,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is False

    assert trader.position is None

    print("PASS: no signal")


# ============================================================
# TEST 4 - ONE POSITION ONLY
# ============================================================

def test_one_position_only():

    print("=" * 60)
    print("TEST 4 - ONE POSITION ONLY")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_one_position.csv",
    )

    first = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert first is True

    second = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert second is False

    assert trader.position is not None

    print("PASS: one-position protection")


# ============================================================
# TEST 5 - SUMMARY
# ============================================================

def test_summary():

    print("=" * 60)
    print("TEST 5 - SUMMARY")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_summary.csv",
    )

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is True

    resolved = trader.resolve_trade(
        winning_side="UP"
    )

    assert resolved is True

    summary = trader.summary()

    assert summary is not None

    assert summary["total_trades"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 0

    print("PASS: summary calculations")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("POLYMARKET BTC PAPER TRADER TEST SUITE")
    print("=" * 60)

    print("PAPER ONLY")
    print("NO API")
    print("NO REAL ORDERS")
    print("NO WALLET")

    print("=" * 60)

    test_winning_trade()

    test_losing_trade()

    test_no_signal()

    test_one_position_only()

    test_summary()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

    print("Strategy engine:      PASS")
    print("Paper trader:         PASS")
    print("Win calculation:      PASS")
    print("Loss calculation:     PASS")
    print("Signal rejection:     PASS")
    print("Position protection:  PASS")
    print("Statistics:            PASS")

    print()
    print("NO REAL TRADING WAS PERFORMED.")

    print("=" * 60)


if __name__ == "__main__":
    main()
