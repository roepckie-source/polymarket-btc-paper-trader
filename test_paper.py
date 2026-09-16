"""
Polymarket BTC Paper Trader
===========================

Integration test.

IMPORTANT:
- PAPER ONLY
- NO API
- NO REAL ORDERS
- NO WALLET
"""

from paper_trader import PaperTrader


def test_winning_trade():
    print("\n" + "=" * 60)
    print("TEST 1 - WINNING TRADE")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_winning.csv",
    )

    opened = trader.open_trade(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        market_price=0.68,
        volatility=0.12,
    )

    assert opened is True, "Trade should have opened"

    assert trader.position is not None, \
        "Position should exist"

    trader.resolve_trade("UP")

    assert trader.position is None, \
        "Position should be closed"

    assert trader.total_trades == 1, \
        "Trade count should be 1"

    assert trader.winning_trades == 1, \
        "There should be 1 winning trade"

    assert trader.losing_trades == 0, \
        "There should be 0 losing trades"

    assert trader.bankroll > 100.00, \
        "Bankroll should increase after a win"

    print("PASS: winning trade")


def test_losing_trade():
    print("\n" + "=" * 60)
    print("TEST 2 - LOSING TRADE")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_losing.csv",
    )

    opened = trader.open_trade(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        market_price=0.68,
        volatility=0.12,
    )

    assert opened is True, "Trade should have opened"

    trader.resolve_trade("DOWN")

    assert trader.position is None, \
        "Position should be closed"

    assert trader.total_trades == 1, \
        "Trade count should be 1"

    assert trader.winning_trades == 0, \
        "There should be 0 winning trades"

    assert trader.losing_trades == 1, \
        "There should be 1 losing trade"

    assert trader.bankroll < 100.00, \
        "Bankroll should decrease after a loss"

    print("PASS: losing trade")


def test_no_signal():
    print("\n" + "=" * 60)
    print("TEST 3 - NO SIGNAL")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_no_signal.csv",
    )

    opened = trader.open_trade(
        btc_open=100000.0,
        btc_current=100010.0,
        seconds_remaining=120,
        market_price=0.68,
        volatility=0.12,
    )

    assert opened is False, \
        "Trade should NOT open"

    assert trader.position is None, \
        "There should be no position"

    assert trader.total_trades == 0, \
        "There should be no completed trades"

    assert trader.bankroll == 100.00, \
        "Bankroll should remain unchanged"

    print("PASS: no signal")


def test_one_position_only():
    print("\n" + "=" * 60)
    print("TEST 4 - ONE POSITION ONLY")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_one_position.csv",
    )

    first = trader.open_trade(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        market_price=0.68,
        volatility=0.12,
    )

    assert first is True, \
        "First trade should open"

    second = trader.open_trade(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=100,
        market_price=0.68,
        volatility=0.12,
    )

    assert second is False, \
        "Second trade must be rejected"

    assert trader.position is not None, \
        "First position must remain open"

    print("PASS: one-position protection")


def test_summary():
    print("\n" + "=" * 60)
    print("TEST 5 - SUMMARY")
    print("=" * 60)

    trader = PaperTrader(
        starting_bankroll=100.00,
        results_file="test_summary.csv",
    )

    trader.open_trade(
        btc_open=100000.0,
        btc_current=100300.0,
        seconds_remaining=120,
        market_price=0.68,
        volatility=0.12,
    )

    trader.resolve_trade("UP")

    stats = trader.summary()

    assert stats["starting_bankroll"] == 100.00

    assert stats["total_trades"] == 1

    assert stats["wins"] == 1

    assert stats["losses"] == 0

    assert stats["current_bankroll"] > 100.00

    assert stats["winrate"] == 1.0

    print("PASS: summary calculations")


# ============================================================
# RUN ALL TESTS
# ============================================================

def main():

    print()
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

    print()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print()
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
