"""Persistent BTC 5-minute spot paper trader. No real order code."""
import csv, json, os
from datetime import datetime, timezone
from pathlib import Path
from okx_market_data import fetch_candles
from okx_paper_config import (
    STARTING_EQUITY_QUOTE, MAX_RISK_QUOTE, MAX_POSITION_QUOTE,
    FEE_RATE, INSTRUMENT, BAR, CANDLE_LIMIT, STOP_DISTANCE,
)

STATE_PATH = Path(os.getenv("PAPER_STATE_PATH", "okx_paper_state.json"))
TRADES_PATH = Path(os.getenv("PAPER_TRADES_PATH", "okx_paper_trades.csv"))
FIELDS = ["time_utc","candle_ts","action","price_usdt","btc","notional_usdt","fee_usdt",
          "cash_usdt","equity_usdt","realized_pnl_usdt","reason"]

def ema(values, period):
    if not values: return []
    alpha = 2.0 / (period + 1)
    result = [float(values[0])]
    for v in values[1:]:
        result.append(alpha * float(v) + (1-alpha) * result[-1])
    return result

def make_signal(candles):
    if len(candles) < 22:
        return "HOLD", "not enough confirmed candles"
    closes = [float(c["close"]) for c in candles]
    avgs = ema(closes, 21)
    if closes[-1] > avgs[-1] and closes[-1] > closes[-2] > closes[-3] > closes[-4]:
        return "BUY", "close above EMA21 and three rising closes"
    if closes[-1] < avgs[-1]:
        return "SELL", "close below EMA21"
    return "HOLD", "no entry/exit condition"

def initial_state():
    return {"cash_usdt": STARTING_EQUITY_QUOTE, "btc": 0.0, "entry_price": None,
            "entry_fee_usdt": 0.0, "stop_price": None, "last_candle_ts": None,
            "equity_peak_usdt": STARTING_EQUITY_QUOTE, "halted": False,
            "updated_at_utc": None}

def load_state():
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            # Compatibility with any previous state file shape
            if "cash_usdt" in data and "btc" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return initial_state()

def save_state(state):
    state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)

def append_trade(row):
    exists = TRADES_PATH.exists()
    with TRADES_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists: w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})

def equity(state, price):
    return float(state["cash_usdt"]) + float(state["btc"]) * float(price)

def step(state, candles, fee_rate=FEE_RATE, max_risk=MAX_RISK_QUOTE,
         max_position=MAX_POSITION_QUOTE, stop_distance=STOP_DISTANCE):
    if not candles: raise ValueError("No confirmed candles received")
    c = candles[-1]; price=float(c["close"]); ts=int(c["ts"])
    if state.get("last_candle_ts") == ts:
        return state, {"action":"NONE","reason":"already processed this candle"}
    state["last_candle_ts"] = ts
    signal, reason = make_signal(candles)
    eq = equity(state, price)
    state["equity_peak_usdt"] = max(float(state.get("equity_peak_usdt", eq)), eq)
    if state.get("halted"):
        return state, {"action":"HALTED","reason":"risk halt is active"}
    if float(state["btc"]) > 0:
        if price <= float(state.get("stop_price") or 0) or signal == "SELL":
            qty=float(state["btc"]); gross=qty*price; exit_fee=gross*fee_rate
            cost=qty*float(state["entry_price"]); entry_fee=float(state.get("entry_fee_usdt", cost*fee_rate))
            pnl=gross-exit_fee-cost-entry_fee
            state["cash_usdt"] += gross-exit_fee
            state.update({"btc":0.0,"entry_price":None,"entry_fee_usdt":0.0,"stop_price":None})
            if pnl < -max_risk - 0.05:
                state["halted"]=True
                reason += "; risk guard triggered (loss can exceed target due to gaps/fees)"
            return state, {"action":"SELL","reason":reason,"price":price,"btc":qty,
                           "notional_usdt":gross,"fee_usdt":exit_fee,"realized_pnl_usdt":pnl}
        return state, {"action":"NONE","reason":"position open; waiting for exit or stop"}
    if signal != "BUY":
        return state, {"action":"NONE","reason":reason}
    notional=min(max_position, max_risk/stop_distance, float(state["cash_usdt"])/(1+fee_rate))
    if notional <= 0:
        state["halted"]=True
        return state, {"action":"HALTED","reason":"insufficient virtual cash"}
    qty=notional/price; fee=notional*fee_rate
    state["cash_usdt"] -= notional+fee
    state.update({"btc":qty,"entry_price":price,"entry_fee_usdt":fee,
                  "stop_price":price*(1-stop_distance)})
    return state, {"action":"BUY","reason":reason,"price":price,"btc":qty,
                   "notional_usdt":notional,"fee_usdt":fee,"realized_pnl_usdt":0.0}

def run_once():
    candles=fetch_candles(INSTRUMENT,BAR,CANDLE_LIMIT)
    state=load_state()
    state,result=step(state,candles)
    price=float(candles[-1]["close"]); eq=equity(state,price)
    print(f"{datetime.now(timezone.utc).isoformat()} | {INSTRUMENT} {BAR} | close={price:.2f} USDT")
    print(f"Action={result['action']} | {result['reason']}")
    print(f"Equity≈{eq:.4f} USDT | cash={state['cash_usdt']:.4f} USDT | BTC={state['btc']:.8f}")
    if result["action"] in ("BUY","SELL"):
        append_trade({
            "time_utc":datetime.now(timezone.utc).isoformat(),"candle_ts":candles[-1]["ts"],
            "action":result["action"],"price_usdt":result["price"],"btc":result["btc"],
            "notional_usdt":result.get("notional_usdt",0),"fee_usdt":result.get("fee_usdt",0),
            "cash_usdt":round(state["cash_usdt"],8),"equity_usdt":round(eq,8),
            "realized_pnl_usdt":round(result.get("realized_pnl_usdt",0),8),"reason":result["reason"]
        })
    save_state(state)
    return state,result

if __name__ == "__main__":
    run_once()
