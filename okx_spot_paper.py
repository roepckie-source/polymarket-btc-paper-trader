"""BTC 5-minute, long-only spot paper trader. No real-order functions or credentials."""
from __future__ import annotations
import csv, json, os, time
from datetime import datetime, timezone
from pathlib import Path
from okx_market_data import fetch_candles
from okx_paper_config import (
    STARTING_EQUITY_EUR, MAX_RISK_EUR, MAX_POSITION_EUR, FEE_RATE,
    INSTRUMENT, BAR, CANDLE_LIMIT, POLL_SECONDS,
)

STATE_PATH = Path(os.getenv("PAPER_STATE_PATH", "okx_paper_state.json"))
TRADES_PATH = Path(os.getenv("PAPER_TRADES_PATH", "okx_paper_trades.csv"))

def ema(values, period):
    if not values:
        return []
    alpha = 2.0 / (period + 1)
    out = [float(values[0])]
    for value in values[1:]:
        out.append(alpha * float(value) + (1-alpha) * out[-1])
    return out

def make_signal(candles):
    """Simple baseline for plumbing tests, not a validated profitable strategy."""
    if len(candles) < 22:
        return "HOLD", "not enough closed candles"
    closes = [c["close"] for c in candles]
    averages = ema(closes, 21)
    # Enter only when price is above EMA and three closed-candle returns are positive.
    rising = closes[-1] > closes[-2] > closes[-3] > closes[-4]
    if closes[-1] > averages[-1] and rising:
        return "BUY", "close above EMA21 and three rising closes"
    if closes[-1] < averages[-1]:
        return "SELL", "close below EMA21"
    return "HOLD", "no entry/exit condition"

def initial_state():
    return {"cash_eur": STARTING_EQUITY_EUR, "btc": 0.0, "entry_price": None,
            "stop_price": None, "last_candle_ts": None, "equity_peak_eur": STARTING_EQUITY_EUR,
            "halted": False}

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return initial_state()

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

def append_trade(row):
    exists = TRADES_PATH.exists()
    with TRADES_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "time_utc","candle_ts","action","price","btc","notional_eur","fee_eur",
            "cash_eur","equity_eur","realized_pnl_eur","reason"
        ])
        if not exists:
            writer.writeheader()
        writer.writerow(row)

def portfolio_equity(state, price):
    # Quote price is USDT; treated as approximate EUR for this first paper prototype.
    # Production-quality accounting must use a live EUR conversion rate.
    return float(state["cash_eur"]) + float(state["btc"]) * price

def step(state, candles, fee_rate=FEE_RATE, max_risk_eur=MAX_RISK_EUR,
         max_position_eur=MAX_POSITION_EUR):
    if not candles:
        raise ValueError("No confirmed candles")
    candle = candles[-1]
    price, candle_ts = float(candle["close"]), int(candle["ts"])
    if state.get("last_candle_ts") == candle_ts:
        return state, {"action":"NONE", "reason":"already processed this candle"}
    state["last_candle_ts"] = candle_ts
    signal, reason = make_signal(candles)
    equity = portfolio_equity(state, price)
    state["equity_peak_eur"] = max(float(state.get("equity_peak_eur", equity)), equity)
    if state.get("halted"):
        return state, {"action":"HALTED", "reason":"manual/risk halt"}
    if state["btc"] > 0:
        # Conservative hard stop at the entry level minus the price move corresponding to €2 risk.
        # Position quantity is chosen so a 2% stop move loses at most the risk budget before fees.
        stop = float(state.get("stop_price") or 0)
        if price <= stop or signal == "SELL":
            qty = float(state["btc"])
            gross = qty * price
            fee = gross * fee_rate
            entry_cost = qty * float(state["entry_price"])
            entry_fee_est = entry_cost * fee_rate
            proceeds = gross - fee
            pnl = proceeds - entry_cost - entry_fee_est
            state["cash_eur"] += proceeds
            state["btc"] = 0.0
            state["entry_price"] = None
            state["stop_price"] = None
            if pnl < -max_risk_eur - 0.05:
                state["halted"] = True
                reason += "; risk guard tripped"
            return state, {"action":"SELL","reason":reason,"price":price,"btc":qty,
                           "notional_eur":gross,"fee_eur":fee,"realized_pnl_eur":pnl}
        return state, {"action":"NONE","reason":"position open; waiting for exit/stop"}
    if signal != "BUY":
        return state, {"action":"NONE","reason":reason}
    # A 2% stop distance sizes the position to lose at most €2 before fees.
    stop_distance = 0.02
    risk_sized_notional = max_risk_eur / stop_distance
    notional = min(max_position_eur, risk_sized_notional, float(state["cash_eur"]) / (1 + fee_rate))
    if notional <= 0:
        state["halted"] = True
        return state, {"action":"HALTED","reason":"insufficient paper cash"}
    qty = notional / price
    fee = notional * fee_rate
    state["cash_eur"] -= notional + fee
    state["btc"] = qty
    state["entry_price"] = price
    state["stop_price"] = price * (1 - stop_distance)
    return state, {"action":"BUY","reason":reason,"price":price,"btc":qty,
                   "notional_eur":notional,"fee_eur":fee,"realized_pnl_eur":0.0}

def run_once():
    candles = fetch_candles(INSTRUMENT, BAR, CANDLE_LIMIT)
    state = load_state()
    old_ts = state.get("last_candle_ts")
    state, result = step(state, candles)
    price = float(candles[-1]["close"])
    equity = portfolio_equity(state, price)
    print(f"{datetime.now(timezone.utc).isoformat()} | {INSTRUMENT} {BAR} | close={price:.2f} USDT")
    print(f"Action={result['action']} | {result['reason']} | equity≈€{equity:.2f} | cash=€{state['cash_eur']:.2f} | BTC={state['btc']:.8f}")
    if result["action"] in ("BUY","SELL"):
        append_trade({
            "time_utc":datetime.now(timezone.utc).isoformat(),"candle_ts":candles[-1]["ts"],
            "action":result["action"],"price":result["price"],"btc":result["btc"],
            "notional_eur":result.get("notional_eur",0),"fee_eur":result.get("fee_eur",0),
            "cash_eur":round(state["cash_eur"],6),"equity_eur":round(equity,6),
            "realized_pnl_eur":round(result.get("realized_pnl_eur",0),6),"reason":result["reason"]
        })
    save_state(state)

def main():
    print("OKX BTC spot PAPER BOT — public market data only; no order endpoints; no API keys.")
    print("NOTE: BTC-USDT is treated as EUR approximately for paper accounting; results are not exact EUR P&L.")
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
