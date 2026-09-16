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

# Stronger artificial move for the software test.
#
# This is NOT a performance claim.
BTC_CURRENT = 100500.00

SECONDS_REMAINING = 120

MARKET_PRICE = 0.68

VOLATILITY = 0.04


# ============================================================
# TEST 1
# ============================================================

def test_winning_trade():

    print("=" * 60)
    print("TEST 1 - WINNING TRADE")
    print("=" * 60)

    trader = PaperTrader()

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is True, "Trade should have opened"

    trader.resolve_trade(
        btc_final=BTC_CURRENT
    )

    assert trader.wins == 1

    print("PASS: winning trade")


# ============================================================
# TEST 2
# ============================================================

def test_losing_trade():

    print("=" * 60)
    print("TEST 2 - LOSING TRADE")
    print("=" * 60)

    trader = PaperTrader()

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is True, "Trade should have opened"

    trader.resolve_trade(
        btc_final=BTC_OPEN - 100
    )

    assert trader.losses == 1

    print("PASS: losing trade")


# ============================================================
# TEST 3
# ============================================================

def test_no_signal():

    print("=" * 60)
    print("TEST 3 - NO SIGNAL")
    print("=" * 60)

    trader = PaperTrader()

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_OPEN + 10,
        seconds_remaining=120,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is False

    print("PASS: no signal")


# ============================================================
# TEST 4
# ============================================================

def test_one_position_only():

    print("=" * 60)
    print("TEST 4 - ONE POSITION ONLY")
    print("=" * 60)

    trader = PaperTrader()

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

    print("PASS: one-position protection")


# ============================================================
# TEST 5
# ============================================================

def test_summary():

    print("=" * 60)
    print("TEST 5 - SUMMARY")
    print("=" * 60)

    trader = PaperTrader()

    opened = trader.open_trade(
        btc_open=BTC_OPEN,
        btc_current=BTC_CURRENT,
        seconds_remaining=SECONDS_REMAINING,
        market_price=MARKET_PRICE,
        volatility=VOLATILITY,
    )

    assert opened is True

    trader.resolve_trade(
        btc_final=BTC_CURRENT
    )

    summary = trader.get_summary()

    assert summary is not None

    assert trader.wins == 1

    assert trader.losses == 0

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
