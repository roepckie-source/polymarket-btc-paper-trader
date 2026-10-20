import unittest
from okx_spot_paper import initial_state, step, make_signal

def candles(closes, start=1_000_000):
    return [{
        "ts": start + i * 300_000, "open": p, "high": p + 1,
        "low": p - 1, "close": p, "volume": 10, "confirmed": True
    } for i, p in enumerate(closes)]

class PaperBotTests(unittest.TestCase):
    def test_not_enough_data_holds(self):
        self.assertEqual(make_signal(candles([100, 101])), ("HOLD", "not enough closed candles"))

    def test_duplicate_candle_no_double_trade(self):
        cs = candles(list(range(100, 125)))
        state, result = step(initial_state(), cs)
        self.assertEqual(state["last_candle_ts"], cs[-1]["ts"])
        state, result = step(state, cs)
        self.assertEqual(result["action"], "NONE")
        self.assertIn("already processed", result["reason"])

    def test_buy_size_respects_cap_and_stop(self):
        cs = candles(list(range(100, 125)))
        state, result = step(initial_state(), cs, max_position_eur=20, max_risk_eur=2)
        self.assertEqual(result["action"], "BUY")
        self.assertLessEqual(result["notional_quote"], 20)
        self.assertAlmostEqual(state["stop_price"], cs[-1]["close"] * 0.98)
        self.assertLessEqual(result["notional_quote"] * 0.02, 2.0)

    def test_stop_closes_position(self):
        cs = candles(list(range(100, 125)))
        state, result = step(initial_state(), cs)
        self.assertEqual(result["action"], "BUY")
        next_cs = candles(list(range(100, 125)) + [cs[-1]["close"] * 0.97], start=1_000_000)
        state, result2 = step(state, next_cs)
        self.assertEqual(result2["action"], "SELL")
        self.assertEqual(state["btc"], 0.0)

    def test_down_signal_does_not_open_short(self):
        cs = candles(list(range(130, 100, -1)))
        state, result = step(initial_state(), cs)
        self.assertNotEqual(result["action"], "SELL")
        self.assertEqual(state["btc"], 0.0)

if __name__ == "__main__":
    unittest.main()
