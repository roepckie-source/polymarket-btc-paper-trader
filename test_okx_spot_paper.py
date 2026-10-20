import unittest
from okx_spot_paper import initial_state, step, portfolio_equity, make_signal

def candles(closes, start=1000000):
    return [{"ts":start+i*300000,"open":p,"high":p+1,"low":p-1,"close":p,"volume":10,"confirmed":True}
            for i,p in enumerate(closes)]

class PaperBotTests(unittest.TestCase):
    def test_not_enough_data_holds(self):
        self.assertEqual(make_signal(candles([100,101])[0:]), ("HOLD","not enough closed candles"))

    def test_duplicate_candle_no_double_trade(self):
        cs = candles(list(range(100,125)))
        s=initial_state()
        s, r=step(s,cs)
        self.assertEqual(s["last_candle_ts"],cs[-1]["ts"])
        s, r2=step(s,cs)
        self.assertEqual(r2["action"],"NONE")
        self.assertIn("already processed",r2["reason"])

    def test_buy_size_respects_cap_and_stop(self):
        cs=candles(list(range(100,125)))
        s=initial_state()
        s,r=step(s,cs,max_position_eur=20,max_risk_eur=2)
        self.assertEqual(r["action"],"BUY")
        self.assertLessEqual(r["notional_eur"],20)
        self.assertAlmostEqual(s["stop_price"],cs[-1]["close"]*0.98)
        self.assertLessEqual(r["notional_eur"]*0.02,2.0)

    def test_stop_closes_position(self):
        cs=candles(list(range(100,125)))
        s,r=step(initial_state(),cs)
        self.assertEqual(r["action"],"BUY")
        next_cs=candles(list(range(100,125))+[cs[-1]["close"]*0.97], start=1000000)
        # ensure new candle timestamp, and below stop
        s,r2=step(s,next_cs)
        self.assertEqual(r2["action"],"SELL")
        self.assertEqual(s["btc"],0.0)

    def test_down_signal_does_not_open_short(self):
        cs=candles(list(range(130,100,-1)))
        s,r=step(initial_state(),cs)
        self.assertNotEqual(r["action"],"SELL")  # no position to sell / no shorting
        self.assertEqual(s["btc"],0.0)

if __name__ == "__main__":
    unittest.main()
