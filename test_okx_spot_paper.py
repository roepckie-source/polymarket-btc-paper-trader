import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from okx_spot_paper import initial_state, step, save_state, load_state, equity, validate_state

def candles(closes, start=1_000_000, lows=None, opens=None):
    out=[]
    for i,p in enumerate(closes):
        p=float(p); lo=float(lows[i]) if lows is not None else p-1
        op=float(opens[i]) if opens is not None else p
        hi=max(p+1,op,lo)
        out.append({"ts":start+i*300_000,"open":op,"high":hi,"low":lo,"close":p,"volume":10,"confirmed":True})
    return out

class PaperBotTests(unittest.TestCase):
    def test_not_enough_data_holds(self):
        _,r=step(initial_state(),candles([100,101,102]))
        self.assertEqual(r["action"],"NONE")
        self.assertIn("not enough",r["reason"])
    def test_buy_respects_cap_and_sets_stop(self):
        cs=candles(list(range(100,125))); s,r=step(initial_state(),cs)
        self.assertEqual(r["action"],"BUY")
        self.assertLessEqual(r["notional_usdt"],20)
        self.assertLessEqual(r["notional_usdt"]+r["fee_usdt"],100)
        self.assertAlmostEqual(s["stop_price"],cs[-1]["close"]*0.98)
    def test_duplicate_candle_does_not_trade_twice(self):
        cs=candles(list(range(100,125))); s,r=step(initial_state(),cs)
        cash,btc=s["cash_usdt"],s["btc"]
        s,r=step(s,cs)
        self.assertEqual(r["action"],"NONE")
        self.assertEqual(s["cash_usdt"],cash); self.assertEqual(s["btc"],btc)
    def test_stop_triggered_by_low(self):
        cs=candles(list(range(100,125))); s,_=step(initial_state(),cs)
        stop=s["stop_price"]; closes=list(range(100,125))+[stop+0.5]
        lows=[float(p)-1 for p in closes]; lows[-1]=stop-0.5
        s,r=step(s,candles(closes,lows=lows))
        self.assertEqual(r["action"],"SELL")
        self.assertAlmostEqual(r["price"],stop)
        self.assertEqual(s["btc"],0.0); self.assertIsNone(s["stop_price"])
        self.assertEqual(s["entry_fee_usdt"],0.0)
    def test_gap_below_stop_uses_open(self):
        cs=candles(list(range(100,125))); s,_=step(initial_state(),cs)
        stop=s["stop_price"]; closes=list(range(100,125))+[stop-3]
        opens=[float(p) for p in closes]; lows=[float(p)-1 for p in closes]
        opens[-1]=stop-2; lows[-1]=stop-4
        s,r=step(s,candles(closes,lows=lows,opens=opens))
        self.assertEqual(r["action"],"SELL")
        self.assertAlmostEqual(r["price"],stop-2)
        self.assertIn("gap-through-stop",r["reason"])
    def test_candle_gap_halts_without_advancing_cursor(self):
        cs=candles(list(range(100,125))); s,_=step(initial_state(),cs)
        old=s["last_candle_ts"]
        later=candles([124],start=old) + candles([130],start=old+600_000)
        s,r=step(s,later)
        self.assertEqual(r["action"],"HALTED"); self.assertTrue(s["halted"])
        self.assertIn("manual recovery required",r["reason"])
        self.assertIn("timestamp gap detected", s["halt_reason"])
        self.assertIsNotNone(s["halted_at_utc"])
        self.assertEqual(s["last_candle_ts"],old)
    def test_state_already_halted_never_trades_or_advances(self):
        s=initial_state(); s["halted"]=True; old=123456
        s["last_candle_ts"]=old
        s,r=step(s,candles(list(range(100,125))))
        self.assertEqual(r["action"],"HALTED")
        self.assertIn("manual review required", r["reason"])
        self.assertEqual(s["last_candle_ts"],old)
    def test_catches_up_contiguous_candles(self):
        first=candles(list(range(100,125)))
        s,_=step(initial_state(),first)
        extra=candles([125,126,127],start=first[-1]["ts"]+300_000)
        s,r=step(s,first+extra)
        self.assertEqual(s["last_candle_ts"],extra[-1]["ts"])
        self.assertEqual(len(r["events"]),3)
    def test_missing_saved_cursor_halts_without_advancing(self):
        s=initial_state(); s["last_candle_ts"]=1
        s,r=step(s,candles(list(range(100,125))))
        self.assertEqual(r["action"],"HALTED"); self.assertTrue(s["halted"])
        self.assertEqual(s["last_candle_ts"],1)
    def test_invalid_state_fails_closed(self):
        with self.assertRaises(ValueError): validate_state({"cash_usdt":100,"btc":0})
    def test_state_save_reload(self):
        s,r=step(initial_state(),candles(list(range(100,125))))
        self.assertEqual(r["action"],"BUY")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"state.json"
            with patch("okx_spot_paper.STATE_PATH",path):
                save_state(s); restored=load_state()
            for k in ("cash_usdt","btc","entry_price","entry_fee_usdt","stop_price","last_candle_ts","halt_reason","halted_at_utc"):
                self.assertEqual(restored[k],s[k])
    def test_equity(self):
        s=initial_state(); s["cash_usdt"]=80; s["btc"]=0.001
        self.assertAlmostEqual(equity(s,20_000),100)

if __name__=="__main__": unittest.main(verbosity=2)
