import unittest, tempfile
from pathlib import Path
import okx_market_maker_paper as mm

def book(bid,ask): return {"inst_id":"BTC-USDT","best_bid":float(bid),"best_ask":float(ask),"mid":(float(bid)+float(ask))/2}

class MarketMakerTests(unittest.TestCase):
    def setUp(self): self.state=mm.initial_state(100)
    def test_initial_equity_and_inventory(self):
        self.assertAlmostEqual(mm.equity(self.state,100),100); self.assertGreater(self.state['btc'],0); self.assertGreater(self.state['cash_usdt'],0)
    def test_quotes_both_sides_and_passive(self):
        s,r=mm.step(self.state,book(99.9,100.1)); self.assertIsNotNone(s['buy_order']); self.assertIsNotNone(s['sell_order']); self.assertLess(s['buy_order']['price'],s['sell_order']['price']); self.assertLessEqual(s['buy_order']['price'],99.9); self.assertGreaterEqual(s['sell_order']['price'],100.1)
    def test_buy_fill_when_ask_crosses_limit(self):
        s,_=mm.step(self.state,book(99.9,100.1)); order=s['buy_order']; s,r=mm.step(s,book(order['price']-0.1,order['price'])); self.assertTrue(any(x['side']=='BUY' for x in r['fills']))
    def test_sell_fill_when_bid_crosses_limit(self):
        s,_=mm.step(self.state,book(99.9,100.1)); order=s['sell_order']; s,r=mm.step(s,book(order['price'],order['price']+0.1)); self.assertTrue(any(x['side']=='SELL' for x in r['fills']))
    def test_small_moves_accumulate_from_last_quote_mid(self):
        s,_=mm.step(self.state,book(99.95,100.05))  # initial quotes at mid 100.00
        old_buy=s["buy_order"]["price"]
        s,_=mm.step(s,book(100.00,100.10))  # mid 100.05: +0.05%
        self.assertEqual(s["buy_order"]["price"],old_buy)
        s,_=mm.step(s,book(100.06,100.16))  # mid 100.11: +0.11% total
        self.assertNotEqual(s["buy_order"]["price"],old_buy)
        self.assertAlmostEqual(s["last_quote_mid"],100.11)

    def test_no_fill_without_crossing(self):
        s,_=mm.step(self.state,book(99.9,100.1)); before=(s['cash_usdt'],s['btc']); s,r=mm.step(s,book(99.8,100.2)); self.assertEqual(r['fills'],[]); self.assertEqual(before,(s['cash_usdt'],s['btc']))
    def test_invalid_book(self):
        with self.assertRaises(ValueError): mm.step(self.state,book(100.2,100.1))
    def test_halted(self):
        self.state['halted']=True; s,r=mm.step(self.state,book(99.9,100.1)); self.assertEqual(r['action'],'HALTED')
    def test_state_roundtrip(self):
        s,_=mm.step(self.state,book(99.9,100.1))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json'; mm.save_state(s,p); restored=mm.load_state(p)
        self.assertEqual(restored['buy_order'],s['buy_order']); self.assertAlmostEqual(restored['btc'],s['btc'])

if __name__=='__main__': unittest.main(verbosity=2)
