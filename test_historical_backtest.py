import unittest
from historical_backtest import run_backtest, load_rows

class HistoricalBacktestTests(unittest.TestCase):
    def test_rejected_rows_do_not_change_bankroll(self):
        rows = [{"timestamp":"t1", "btc_open":"100", "btc_current":"100.01",
                 "seconds_remaining":"120", "up_price":"0.51", "outcome":"UP"}]
        trades, summary = run_backtest(rows)
        self.assertFalse(trades[0]["signal"])
        self.assertEqual(summary["trades"], 0)
        self.assertEqual(summary["ending_bankroll"], 100.0)


    def test_uses_market_price_for_btc_direction(self):
        # BTC moves down, so strategy must be priced against DOWN, not UP.
        rows = [{"timestamp":"t1", "btc_open":"100", "btc_current":"99.8",
                 "seconds_remaining":"120", "up_price":"0.30", "down_price":"0.70",
                 "outcome":"DOWN"}]
        trades, summary = run_backtest(rows)
        self.assertEqual(trades[0]["market_price"], 0.70)
        self.assertEqual(trades[0]["side"], "DOWN")

    def test_invalid_outcome_rejected(self):
        rows = [{"timestamp":"t1", "btc_open":"100", "btc_current":"100.01",
                 "seconds_remaining":"120", "up_price":"0.51", "outcome":"UNKNOWN"}]
        with self.assertRaises(ValueError):
            run_backtest(rows)

    def test_missing_columns_rejected(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", delete=False, newline="") as f:
            f.write("timestamp,btc_open\nt1,100\n")
            name = f.name
        try:
            with self.assertRaises(ValueError):
                load_rows(name)
        finally:
            os.unlink(name)

if __name__ == "__main__":
    unittest.main()
