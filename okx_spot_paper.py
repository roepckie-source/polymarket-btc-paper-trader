"""Persistent BTC 5-minute spot paper trader; public data only, no order code."""
import csv, json, math, os
from datetime import datetime, timezone
from pathlib import Path
from okx_market_data import fetch_candles
from okx_paper_config import STARTING_EQUITY_QUOTE, MAX_RISK_QUOTE, MAX_POSITION_QUOTE, FEE_RATE, INSTRUMENT, BAR, CANDLE_LIMIT, STOP_DISTANCE

STATE_PATH = Path(os.getenv("PAPER_STATE_PATH", "okx_paper_state.json"))
TRADES_PATH = Path(os.getenv("PAPER_TRADES_PATH", "okx_paper_trades.csv"))
FIELDS = ["time_utc","candle_ts","action","price_usdt","btc","notional_usdt","fee_usdt","cash_usdt","equity_usdt","realized_pnl_usdt","reason"]
FIVE_MINUTES_MS = 300_000

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def ema(values, period):
    if not values: return []
    alpha = 2.0 / (period + 1)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1-alpha) * result[-1])
    return result

def make_signal(candles):
    if len(candles) < 22: return "HOLD", "not enough confirmed candles"
    closes = [float(c["close"]) for c in candles]
    averages = ema(closes, 21)
    if closes[-1] > averages[-1] and closes[-1] > closes[-2] > closes[-3] > closes[-4]:
        return "BUY", "close above EMA21 and three rising closes"
    if closes[-1] < averages[-1]: return "SELL", "close below EMA21"
    return "HOLD", "no entry/exit condition"

def initial_state():
    return {"cash_usdt":float(STARTING_EQUITY_QUOTE),"btc":0.0,"entry_price":None,
            "entry_fee_usdt":0.0,"stop_price":None,"last_candle_ts":None,
            "equity_peak_usdt":float(STARTING_EQUITY_QUOTE),"halted":False,"updated_at_utc":None}

def validate_state(data):
    required = ("cash_usdt","btc","entry_price","entry_fee_usdt","stop_price","last_candle_ts","equity_peak_usdt","halted")
    if not isinstance(data, dict) or any(k not in data for k in required):
        raise ValueError("Paper state is missing required fields")
    for k in ("cash_usdt","btc","entry_fee_usdt","equity_peak_usdt"):
        v = data[k]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError(f"Invalid numeric state field: {k}")
    if data["cash_usdt"] < 0 or data["btc"] < 0 or data["entry_fee_usdt"] < 0:
        raise ValueError("Paper state contains negative balances")
    if not isinstance(data["halted"],bool): raise ValueError("halted must be boolean")
    if data["last_candle_ts"] is not None and (isinstance(data["last_candle_ts"],bool) or not isinstance(data["last_candle_ts"],int)):
        raise ValueError("last_candle_ts must be an integer or null")
    if data["btc"] > 0:
        if data["entry_price"] is None or data["stop_price"] is None:
            raise ValueError("Open position is missing entry or stop price")
        for k in ("entry_price","stop_price"):
            if isinstance(data[k],bool) or not math.isfinite(float(data[k])) or float(data[k]) <= 0:
                raise ValueError(f"Invalid open-position field: {k}")
    elif data["entry_price"] is not None or data["stop_price"] is not None:
        raise ValueError("Flat account must not retain entry or stop price")
    return data

def load_state():
    if not STATE_PATH.exists():
        print("No existing paper state; initializing a new paper account.")
        return initial_state()
    try:
        return validate_state(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except (json.JSONDecodeError,OSError,TypeError,ValueError) as exc:
        raise RuntimeError(f"Cannot safely load paper state at {STATE_PATH}; evaluation stopped. Inspect or restore the file.") from exc

def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at_utc"] = utc_now()
    temp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(STATE_PATH)

def ensure_trade_log():
    TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TRADES_PATH.exists() or TRADES_PATH.stat().st_size == 0:
        with TRADES_PATH.open("w",newline="",encoding="utf-8") as f:
            csv.DictWriter(f,fieldnames=FIELDS).writeheader()

def append_trade(row):
    ensure_trade_log()
    with TRADES_PATH.open("a",newline="",encoding="utf-8") as f:
        csv.DictWriter(f,fieldnames=FIELDS).writerow({k:row.get(k,"") for k in FIELDS})

def equity(state, price):
    return float(state["cash_usdt"]) + float(state["btc"]) * float(price)

def validate_candle(c):
    for k in ("ts","open","high","low","close"):
        if k not in c: raise ValueError(f"Candle missing {k}")
    ts=int(c["ts"])
    if ts < 0: raise ValueError("Candle timestamp must be non-negative")
    for k in ("open","high","low","close"):
        v=float(c[k])
        if not math.isfinite(v) or v <= 0: raise ValueError(f"Candle {k} must be finite and positive")
    if float(c["low"]) > float(c["high"]): raise ValueError("Candle low exceeds high")
    if not float(c["low"]) <= float(c["open"]) <= float(c["high"]): raise ValueError("Candle open outside low/high")
    if not float(c["low"]) <= float(c["close"]) <= float(c["high"]): raise ValueError("Candle close outside low/high")

def _process_one(state, history, fee_rate, max_risk, max_position, stop_distance):
    candle=history[-1]
    price=float(candle["close"]); ts=int(candle["ts"])
    state["last_candle_ts"]=ts
    mark=equity(state,price)
    state["equity_peak_usdt"]=max(float(state.get("equity_peak_usdt",mark)),mark)
    signal,reason=make_signal(history)
    if float(state["btc"])>0:
        stop=state.get("stop_price")
        stop_hit=stop is not None and float(candle["low"])<=float(stop)
        if stop_hit:
            op=float(candle["open"])
            exec_price=min(op,float(stop))
            exit_reason=("simulated stop triggered; gap-through-stop modeled at candle open"
                         if op<float(stop) else "simulated stop triggered by candle low")
        elif signal=="SELL":
            exec_price=price; exit_reason=reason
        else:
            return {"action":"NONE","reason":"position open; waiting for exit or stop","candle_ts":ts}
        qty=float(state["btc"]); gross=qty*exec_price; exit_fee=gross*fee_rate
        pnl=gross-exit_fee-qty*float(state["entry_price"])-float(state.get("entry_fee_usdt",0))
        state["cash_usdt"] += gross-exit_fee
        state.update({"btc":0.0,"entry_price":None,"entry_fee_usdt":0.0,"stop_price":None})
        if pnl < -float(max_risk):
            state["halted"]=True; exit_reason += "; risk threshold exceeded; loss can exceed target"
        return {"action":"SELL","reason":exit_reason,"price":exec_price,"btc":qty,
                "notional_usdt":gross,"fee_usdt":exit_fee,"realized_pnl_usdt":pnl,"candle_ts":ts}
    if signal!="BUY": return {"action":"NONE","reason":reason,"candle_ts":ts}
    notional=min(float(max_position),float(max_risk)/stop_distance,float(state["cash_usdt"])/(1+fee_rate))
    if notional<=0:
        state["halted"]=True
        return {"action":"HALTED","reason":"insufficient virtual cash","candle_ts":ts}
    qty=notional/price; fee=notional*fee_rate
    state["cash_usdt"]-=notional+fee
    state.update({"btc":qty,"entry_price":price,"entry_fee_usdt":fee,"stop_price":price*(1-stop_distance)})
    return {"action":"BUY","reason":reason,"price":price,"btc":qty,"notional_usdt":notional,"fee_usdt":fee,"realized_pnl_usdt":0.0,"candle_ts":ts}

def step(state,candles,fee_rate=FEE_RATE,max_risk=MAX_RISK_QUOTE,max_position=MAX_POSITION_QUOTE,stop_distance=STOP_DISTANCE):
    if state.get("halted"):
        return state,{"action":"HALTED","reason":"risk halt is active; manual review required"}
    if not candles: raise ValueError("No confirmed candles received")
    if not 0 <= fee_rate < 1: raise ValueError("fee_rate must be between 0 and 1")
    if max_risk <= 0 or max_position <= 0: raise ValueError("Risk and position limits must be positive")
    if not 0 < stop_distance < 1: raise ValueError("stop_distance must be between 0 and 1")
    ordered=sorted(candles,key=lambda c:int(c["ts"]))
    for c in ordered: validate_candle(c)
    if len({int(c["ts"]) for c in ordered}) != len(ordered):
        raise ValueError("Duplicate candle timestamps received")
    prev=state.get("last_candle_ts")
    if prev is None:
        # On first launch, do not replay old history as if it were live decisions.
        todo=[ordered[-1]]
        histories=[ordered]
    else:
        prev=int(prev)
        matches=[i for i,c in enumerate(ordered) if int(c["ts"])==prev]
        if not matches:
            state["halted"]=True
            return state,{"action":"HALTED","reason":"last processed candle is outside fetched history; manual recovery required"}
        start=matches[-1]
        todo=ordered[start+1:]
        histories=[ordered[:start+2+i] for i in range(len(todo))]
        if not todo:
            return state,{"action":"NONE","reason":"already processed latest candle"}
        # Check every candle from the saved cursor forward before processing anything.
        expected=prev
        for c in todo:
            ts=int(c["ts"])
            if ts-expected != FIVE_MINUTES_MS:
                state["halted"]=True
                return state,{"action":"HALTED","reason":"candle gap detected; cursor preserved; manual recovery required"}
            expected=ts
    events=[]
    for hist in histories:
        result=_process_one(state,hist,fee_rate,max_risk,max_position,stop_distance)
        events.append(result)
        if state.get("halted"):
            break
    final=events[-1]
    final["events"]=events
    return state,final

def run_once():
    ensure_trade_log()
    candles=fetch_candles(INSTRUMENT,BAR,CANDLE_LIMIT)
    if not candles: raise ValueError("Market data returned no confirmed candles")
    state=load_state()
    state,result=step(state,candles)
    price=float(candles[-1]["close"]); mark=equity(state,price)
    print(f"{utc_now()} | {INSTRUMENT} {BAR} | close={price:.2f} USDT")
    print(f"Action={result['action']} | {result['reason']}")
    print(f"Equity={mark:.4f} USDT | cash={state['cash_usdt']:.4f} USDT | BTC={state['btc']:.8f}")
    for event in result.get("events",[result]):
        if event["action"] in ("BUY","SELL"):
            event_ts=event.get("candle_ts",candles[-1]["ts"])
            # Find the mark price for the candle on which the event occurred.
            event_candle=next((c for c in candles if int(c["ts"])==int(event_ts)),candles[-1])
            append_trade({"time_utc":utc_now(),"candle_ts":event_ts,"action":event["action"],
                "price_usdt":event["price"],"btc":event["btc"],"notional_usdt":event.get("notional_usdt",0),
                "fee_usdt":event.get("fee_usdt",0),"cash_usdt":round(state["cash_usdt"],8),
                "equity_usdt":round(equity(state,event_candle["close"]),8),
                "realized_pnl_usdt":round(event.get("realized_pnl_usdt",0),8),"reason":event["reason"]})
    save_state(state)
    return state,result

if __name__=="__main__": run_once()
