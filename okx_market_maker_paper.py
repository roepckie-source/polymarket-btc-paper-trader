"""OKX BTC-USDT market-making paper simulator. No private API or live order code."""
from __future__ import annotations
import csv, json, math, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests
from okx_mm_config import *

PUBLIC_BOOK_URL = "https://www.okx.com/api/v5/market/books"
TRADE_FIELDS = ["time_utc","event","side","price","quantity","notional_usdt","fee_usdt","realized_pnl_usdt","cash_usdt","btc","mid_price","equity_usdt","detail"]
EVENT_FIELDS = ["time_utc","mid_price","best_bid","best_ask","spread_pct","buy_quote","sell_quote","cash_usdt","btc","equity_usdt","realized_pnl_usdt","detail"]

def utc_now(): return datetime.now(timezone.utc).isoformat()

def fetch_orderbook(inst_id=INSTRUMENT, timeout=10.0):
    """Read only OKX's public order-book endpoint."""
    r=requests.get(PUBLIC_BOOK_URL, params={"instId":inst_id,"sz":str(ORDERBOOK_DEPTH)}, timeout=timeout, headers={"User-Agent":"OKX-Market-Maker-Paper/1.0"})
    r.raise_for_status(); payload=r.json()
    if payload.get("code") != "0" or not payload.get("data"): raise RuntimeError(f"OKX public order book error: {payload!r}")
    b=payload["data"][0]; bids=b.get("bids",[]); asks=b.get("asks",[])
    if not bids or not asks: raise RuntimeError("Order book has no bid/ask levels")
    bid=float(bids[0][0]); ask=float(asks[0][0])
    if not (math.isfinite(bid) and math.isfinite(ask) and 0 < bid < ask): raise RuntimeError("Invalid/crossed order book")
    return {"inst_id":inst_id,"best_bid":bid,"best_ask":ask,"mid":(bid+ask)/2,"timestamp":b.get("ts")}

def round_down(x, step):
    if step <= 0: raise ValueError("step must be positive")
    return math.floor((x+1e-12)/step)*step

def initial_state(mid):
    if not math.isfinite(mid) or mid <= 0: raise ValueError("mid must be positive")
    cash=STARTING_EQUITY_USDT*INITIAL_CASH_FRACTION; btc=(STARTING_EQUITY_USDT-cash)/mid
    return {"version":1,"instrument":INSTRUMENT,"cash_usdt":cash,"btc":btc,"btc_cost_usdt":btc*mid,"realized_pnl_usdt":0.0,"starting_equity_usdt":STARTING_EQUITY_USDT,"equity_peak_usdt":STARTING_EQUITY_USDT,"halted":False,"buy_order":None,"sell_order":None,"last_mid":mid,"initialized":True,"created_at_utc":utc_now(),"updated_at_utc":utc_now()}

def validate_state(s):
    required={"version","instrument","cash_usdt","btc","btc_cost_usdt","realized_pnl_usdt","starting_equity_usdt","equity_peak_usdt","halted","buy_order","sell_order","last_mid"}
    if not isinstance(s,dict) or not required.issubset(s): raise ValueError("Paper state missing required fields")
    for k in ("cash_usdt","btc","btc_cost_usdt","realized_pnl_usdt","starting_equity_usdt","equity_peak_usdt","last_mid"):
        v=s[k]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError(f"Invalid numeric field: {k}")
    if s["cash_usdt"] < -1e-8 or s["btc"] < -1e-12 or s["btc_cost_usdt"] < -1e-8: raise ValueError("Negative paper balance/inventory")
    if not isinstance(s["halted"],bool): raise ValueError("halted must be boolean")
    for k in ("buy_order","sell_order"):
        o=s[k]
        if o is not None and (not isinstance(o,dict) or o.get("side") not in ("BUY","SELL") or any(float(o.get(x,0)) <= 0 for x in ("price","quantity"))): raise ValueError(f"Invalid {k}")
    return s

def equity(s, mid): return float(s["cash_usdt"])+float(s["btc"])*float(mid)
def average_cost(s): return float(s["btc_cost_usdt"])/float(s["btc"]) if s["btc"] > 0 else 0.0

def _csv(path, fields, row):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); fresh=not p.exists() or p.stat().st_size==0
    with p.open("a",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        if fresh: w.writeheader()
        w.writerow({k:row.get(k,"") for k in fields})

def _log_fill(s,b,side,price,qty,fee,pnl):
    _csv(TRADES_PATH,TRADE_FIELDS,{"time_utc":utc_now(),"event":"FILL","side":side,"price":price,"quantity":qty,"notional_usdt":price*qty,"fee_usdt":fee,"realized_pnl_usdt":pnl,"cash_usdt":s["cash_usdt"],"btc":s["btc"],"mid_price":b["mid"],"equity_usdt":equity(s,b["mid"]),"detail":"Simulated fill after public book crossed limit; queue/partial fills not modeled"})

def _log_snapshot(s,b,detail):
    _csv(EVENTS_PATH,EVENT_FIELDS,{"time_utc":utc_now(),"mid_price":b["mid"],"best_bid":b["best_bid"],"best_ask":b["best_ask"],"spread_pct":(b["best_ask"]-b["best_bid"])/b["mid"]*100,"buy_quote":(s.get("buy_order") or {}).get("price",""),"sell_quote":(s.get("sell_order") or {}).get("price",""),"cash_usdt":s["cash_usdt"],"btc":s["btc"],"equity_usdt":equity(s,b["mid"]),"realized_pnl_usdt":s["realized_pnl_usdt"],"detail":detail})

def _fill(s,b,side):
    key="buy_order" if side=="BUY" else "sell_order"; o=s.get(key)
    if not o: return None
    price=float(o["price"]); qty=float(o["quantity"])
    # Require the observed opposite top-of-book to cross the resting limit.
    crossed=float(b["best_ask"]) <= price if side=="BUY" else float(b["best_bid"]) >= price
    if not crossed: return None
    qty=round_down(qty,10**(-QTY_DECIMALS))
    if side=="BUY":
        qty=min(qty,round_down(float(s["cash_usdt"])/(price*(1+MAKER_FEE_RATE)),10**(-QTY_DECIMALS)))
        notional=price*qty; fee=notional*MAKER_FEE_RATE
        if qty <= 0 or notional+fee > s["cash_usdt"]+1e-8: s[key]=None; return None
        s["cash_usdt"]-=notional+fee; s["btc"]+=qty; s["btc_cost_usdt"]+=notional+fee; pnl=0.0
    else:
        qty=round_down(min(qty,float(s["btc"])),10**(-QTY_DECIMALS))
        if qty <= 0: s[key]=None; return None
        notional=price*qty; fee=notional*MAKER_FEE_RATE; basis=average_cost(s)*qty
        s["cash_usdt"]+=notional-fee; s["btc"]-=qty; s["btc_cost_usdt"]=max(0.0,s["btc_cost_usdt"]-basis)
        pnl=notional-fee-basis; s["realized_pnl_usdt"]+=pnl
    s[key]=None; _log_fill(s,b,side,price,qty,fee,pnl)
    return {"side":side,"price":price,"quantity":qty,"fee":fee,"realized_pnl":pnl}

def _quote(s,b):
    mid=float(b["mid"]); half=TARGET_SPREAD_PCT/2
    buy=round_down(min(mid*(1-half),float(b["best_bid"])),PRICE_TICK)
    sell=math.ceil((max(mid*(1+half),float(b["best_ask"]))-1e-12)/PRICE_TICK)*PRICE_TICK
    if buy <= 0 or sell <= buy: raise RuntimeError("Unsafe/crossed quote prices")
    inventory=float(s["btc"])*mid; cash=float(s["cash_usdt"])
    buy_notional=min(ORDER_NOTIONAL_USDT,cash/(1+MAKER_FEE_RATE),max(0.0,MAX_INVENTORY_VALUE_USDT-inventory))
    buy_qty=round_down(buy_notional/buy,10**(-QTY_DECIMALS))
    sell_qty=round_down(min(float(s["btc"]),ORDER_NOTIONAL_USDT/sell),10**(-QTY_DECIMALS))
    s["buy_order"]={"side":"BUY","price":buy,"quantity":buy_qty} if buy_qty*buy >= MIN_ORDER_NOTIONAL_USDT else None
    s["sell_order"]={"side":"SELL","price":sell,"quantity":sell_qty} if sell_qty*sell >= MIN_ORDER_NOTIONAL_USDT else None
    return "two-sided quotes placed" if s["buy_order"] and s["sell_order"] else "one side unavailable: cash/inventory/minimum-notional limit"

def step(s,b):
    s=validate_state(s); bid=float(b["best_bid"]); ask=float(b["best_ask"]); mid=float(b["mid"])
    if not (0 < bid < ask and math.isfinite(mid) and mid > 0): raise ValueError("Invalid book snapshot")
    if s["halted"]: return s,{"action":"HALTED","reason":"drawdown halt active","fills":[]}
    fills=[]
    for side in ("BUY","SELL"):
        event=_fill(s,b,side)
        if event: fills.append(event)
    mark=equity(s,mid); s["equity_peak_usdt"]=max(float(s["equity_peak_usdt"]),mark)
    dd=1-mark/float(s["equity_peak_usdt"])
    if dd >= MAX_DRAWDOWN_PCT:
        s.update({"halted":True,"buy_order":None,"sell_order":None}); detail=f"drawdown {dd:.2%} reached halt threshold"
        _log_snapshot(s,b,detail); return s,{"action":"HALTED","reason":detail,"fills":fills}
    moved=abs(mid/float(s["last_mid"])-1) >= REPRICE_THRESHOLD_PCT
    if fills or moved or (s.get("buy_order") is None and s.get("sell_order") is None): detail=_quote(s,b)
    else: detail="quotes kept resting; midpoint move below reprice threshold"
    if s.get("buy_order") and s.get("sell_order") and s["buy_order"]["price"] >= s["sell_order"]["price"]: raise RuntimeError("BUY quote must be below SELL quote")
    if s.get("sell_order") and s["sell_order"]["quantity"] > s["btc"]+1e-9: raise RuntimeError("SELL quote exceeds virtual BTC inventory")
    if s.get("buy_order") and s["buy_order"]["price"]*s["buy_order"]["quantity"]*(1+MAKER_FEE_RATE) > s["cash_usdt"]+1e-8: raise RuntimeError("BUY quote exceeds virtual cash")
    s["last_mid"]=mid; s["updated_at_utc"]=utc_now(); _log_snapshot(s,b,detail)
    return s,{"action":"FILL" if fills else ("QUOTE" if s.get("buy_order") and s.get("sell_order") else "HOLD"),"reason":detail,"fills":fills,"mid":mid,"buy_order":s.get("buy_order"),"sell_order":s.get("sell_order"),"cash_usdt":s["cash_usdt"],"btc":s["btc"],"equity_usdt":equity(s,mid),"realized_pnl_usdt":s["realized_pnl_usdt"]}

def load_state(path=STATE_PATH,mid=None):
    p=Path(path)
    if not p.exists():
        if mid is None: raise ValueError("mid required to initialize paper account")
        return initial_state(mid)
    return validate_state(json.loads(p.read_text(encoding="utf-8")))

def save_state(s,path=STATE_PATH):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); s["updated_at_utc"]=utc_now(); tmp=p.with_suffix(p.suffix+".tmp"); tmp.write_text(json.dumps(s,indent=2),encoding="utf-8"); tmp.replace(p)

def run_once():
    b=fetch_orderbook(); s=load_state(mid=b["mid"]); s,r=step(s,b); save_state(s)
    print(f"{utc_now()} | {INSTRUMENT} bid={b['best_bid']:.2f} ask={b['best_ask']:.2f} mid={b['mid']:.2f}")
    print(f"Action={r['action']} | {r['reason']} | BUY={s.get('buy_order')} | SELL={s.get('sell_order')}")
    print(f"cash={s['cash_usdt']:.4f} USDT | BTC={s['btc']:.8f} | equity={equity(s,b['mid']):.4f} USDT | realized P&L={s['realized_pnl_usdt']:.4f} USDT")
    return s,r

def run_loop(minutes=30,poll_seconds=POLL_SECONDS):
    if minutes <= 0 or poll_seconds < 1: raise ValueError("minutes and poll_seconds must be positive")
    end=time.monotonic()+minutes*60
    while time.monotonic() < end:
        try:
            _,r=run_once()
            if r.get("action")=="HALTED": print("Risk halt; stopping for manual review."); break
        except Exception as exc: print(f"{utc_now()} | DATA/ENGINE ERROR: {type(exc).__name__}: {exc}")
        remaining=end-time.monotonic()
        if remaining > 0: time.sleep(min(poll_seconds,remaining))

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description="OKX spot market maker - PAPER ONLY")
    p.add_argument("--once",action="store_true"); p.add_argument("--minutes",type=float,default=30); p.add_argument("--poll-seconds",type=int,default=POLL_SECONDS)
    a=p.parse_args()
    run_once() if a.once else run_loop(a.minutes,a.poll_seconds)
