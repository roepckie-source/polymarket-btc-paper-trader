
import unittest
from btc_sma200_backtest import backtest


def make_candles(closes):
    rows = []
    for i, close in enumerate(closes):
        rows.append({
            "timestamp": 1_600_000_000 + i * 86400,
            "open": close,
            "close": close,
        })
    return rows


class SMA200Tests(unittest.TestCase):
    def test_requires_at_least_220_candles(self):
        with self.assertRaises(ValueError):
            backtest(make_candles([100.0] * 219))

    def test_flat_market_does_not_create_trades(self):
        trades, summary, curve = backtest(make_candles([100.0] * 240))
        self.assertEqual(trades, [])
        self.assertEqual(summary["ending_equity"], 1000.0)
        self.assertEqual(summary["completed_trades"], 0)
        self.assertEqual(len(curve), 240)

    def test_buy_and_sell_signals_execute_next_candle_open(self):
        closes = [100.0] * 220 + [120.0] * 4 + [80.0] * 4
        candles = make_candles(closes)
        candles[221]["open"] = 121.0
        candles[225]["open"] = 79.0

        trades, summary, _ = backtest(
            candles, fee_rate=0.0, slippage_rate=0.0
        )
        self.assertEqual([t["action"] for t in trades], ["BUY", "SELL"])
        self.assertEqual(trades[0]["price"], 121.0)
        self.assertEqual(trades[1]["price"], 79.0)
        self.assertEqual(summary["completed_trades"], 1)

    def test_invalid_costs_rejected(self):
        with self.assertRaises(ValueError):
            backtest(make_candles([100.0] * 220), fee_rate=-0.01)


if __name__ == "__main__":
    unittest.main()
