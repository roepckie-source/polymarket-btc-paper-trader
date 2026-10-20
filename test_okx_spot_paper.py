import unittest
from okx_spot_paper import initial_state, step, make_signal

def candles(closes, start=1_000_000):
    return [{"ts":start+i*300000,"open":p,"high":p+1,"low":p-1,"close":p,"volume":10,"confirmed":True}
            for i,p in enumerate(closes)]

class PaperBotTests(unittest.TestCase):
    def test_not_enough_data_holds(self):
        self.assertEqual(make_signal(candles([100,101])),("HOLD","not enough confirmed candles"))
    def test_duplicate_candle_no_double_trade(self):
        cs=candles(list(range(100,125))); state,result=step(initial_state(),cs)
        state,result=step(state,cs)
        self.assertEqual(result["action"],"NONE")
        self.assertIn("already processed",result["reason"])
    def test_buy_size_respects_cap_and_stop(self):
        cs=candles(list(range(100,125))); state,result=step(initial_state(),cs)
        self.assertEqual(result["action"],"BUY")
        self.assertLessEqual(result["notional_usdt"],20)
        self.assertAlmostEqual(state["stop_price"],cs[-1]["close"]*.98)
    def test_stop_closes_position(self):
        cs=candles(list(range(100,125))); state,result=step(initial_state(),cs)
        next_cs=candles(list(range(100,125))+[cs[-1]["close"]*.97])
        state,result=step(state,next_cs)
        self.assertEqual(result["action"],"SELL")
        self.assertEqual(state["btc"],0)
    def test_no_shorting(self):
        cs=candles(list(range(130,100,-1))); state,result=step(initial_state(),cs)
        self.assertEqual(state["btc"],0)
        self.assertNotEqual(result["action"],"SELL")

if __name__ == "__main__": unittest.main()
