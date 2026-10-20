"""BTC 5-minute long-only spot paper trader. No live trading code."""
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from okx_market_data import fetch_candles
from okx_paper_config import (
    STARTING_EQUITY_EUR, MAX_RISK_EUR, MAX_POSITION_EUR, FEE_RATE,
    INSTRUMENT, BAR, CANDLE_LIMIT, POLL_SECONDS, STOP_DISTANCE,
)

STATE_PATH = Path(os.getenv("PAPER_STATE_PATH", "okx_paper_state.json"))
TRADES_PATH = Path(os.getenv("PAPER_TRADES_PATH", "okx_paper_trades.csv"))
TRADE_FIELDS = [
    "time_utc", "candle_ts", "action", "price_usdt", "btc", "notional_usdt",
    "fee_quote", "cash_quote", "equity_quote", "realized_pnl_quote", "reason",
]

def ema(values, period):
    if not values:
        return []
    alpha = 2.0 / (period + 1)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1 - alpha) * result[-1])
    return result

def make_signal(candles):
    """Simple plumbing baseline; not a validated profitable strategy."""
    if len(candles) < 22:
        return "HOLD", "not enough closed candles"
    closes = [float(c["close"]) for c in candles]
    averages = ema(closes, 21)
    rising = closes[-1] > closes[-2] > closes[-3] > closes[-4]
    if closes[-1] > averages[-1] and rising:
        return "BUY", "close above EMA21 and three rising closes"
    if closes[-1] < averages[-1]:
        return "SELL", "close below EMA21"
    return "HOLD", "no entry/exit condition"

def initial_state():
    return {
        "cash_quote": STARTING_EQUITY_EUR,
        "btc": 0.0,
        "entry_price": None,
        "entry_fee_quote": 0.0,
        "stop_price": None,
        "last_candle_ts": None,
        "equity_peak_quote": STARTING_EQUITY_EUR,
        "halted": False,
    }

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return initial_state()

def save_state(state):
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)

def append_trade(row):
    exists = TRADES_PATH.exists()
    with TRADES_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRADE_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in TRADE_FIELDS})

def portfolio_equity(state, price):
    return float(state["cash_quote"]) + float(state["btc"]) * float(price)

def step(state, candles, fee_rate=FEE_RATE, max_risk_eur=MAX_RISK_EUR,
         max_position_eur=MAX_POSITION_EUR, stop_distance=STOP_DISTANCE):
    if not candles:
        raise ValueError("No confirmed candles received")
    candle = candles[-1]
    price, candle_ts = float(candle["close"]), int(candle["ts"])
    if state.get("last_candle_ts") == candle_ts:
        return state, {"action": "NONE", "reason": "already processed this candle"}
    state["last_candle_ts"] = candle_ts
    signal, reason = make_signal(candles)
    equity = portfolio_equity(state, price)
    state["equity_peak_quote"] = max(float(state.get("equity_peak_quote", equity)), equity)
    if state.get("halted"):
        return state, {"action": "HALTED", "reason": "paper risk halt is active"}
    if float(state["btc"]) > 0:
        stop = float(state.get("stop_price") or 0)
        if price <= stop or signal == "SELL":
            qty = float(state["btc"])
            gross = qty * price
            exit_fee = gross * fee_rate
            entry_cost = qty * float(state["entry_price"])
            entry_fee = float(state.get("entry_fee_quote", entry_cost * fee_rate))
            proceeds = gross - exit_fee
            pnl = proceeds - entry_cost - entry_fee
            state["cash_quote"] += proceeds
            state["btc"] = 0.0
            state["entry_price"] = None
            state["entry_fee_quote"] = 0.0
            state["stop_price"] = None
            if pnl < -max_risk_eur - 0.05:
                state["halted"] = True
                reason += "; risk guard tripped (loss can exceed target due to gaps/fees)"
            return state, {
                "action": "SELL", "reason": reason, "price": price, "btc": qty,
                "notional_quote": gross, "fee_quote": exit_fee, "realized_pnl_quote": pnl,
            }
        return state, {"action": "NONE", "reason": "position open; waiting for exit or stop"}
    if signal != "BUY":
        return state, {"action": "NONE", "reason": reason}
    # Risk sizing assumes a 2% stop distance; cap notional to €20 and available virtual cash.
    risk_sized_notional = max_risk_eur / stop_distance
    notional = min(max_position_eur, risk_sized_notional,
                   float(state["cash_quote"]) / (1 + fee_rate))
    if notional <= 0:
        state["halted"] = True
        return state, {"action": "HALTED", "reason": "insufficient paper cash"}
    qty = notional / price
    entry_fee = notional * fee_rate
    state["cash_quote"] -= notional + entry_fee
    state["btc"] = qty
    state["entry_price"] = price
    state["entry_fee_quote"] = entry_fee
    state["stop_price"] = price * (1 - stop_distance)
    return state, {
        "action": "BUY", "reason": reason, "price": price, "btc": qty,
        "notional_quote": notional, "fee_quote": entry_fee, "realized_pnl_quote": 0.0,
    }

def run_once():
    candles = fetch_candles(INSTRUMENT, BAR, CANDLE_LIMIT)
    state = load_state()
    state, result = step(state, candles)
    price = float(candles[-1]["close"])
    equity = portfolio_equity(state, price)
    print(f"{datetime.now(timezone.utc).isoformat()} | {INSTRUMENT} {BAR} | close={price:.2f} USDT")
    print(f"Action={result['action']} | {result['reason']}")
    print(f"Paper equity≈{equity:.2f} quote units | cash={state['cash_quote']:.2f} | BTC={state['btc']:.8f}")
    if result["action"] in ("BUY", "SELL"):
        append_trade({
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "candle_ts": candles[-1]["ts"],
            "action": result["action"],
            "price_usdt": result["price"],
            "btc": result["btc"],
            "notional_usdt": result.get("notional_quote", 0),
            "fee_quote": result.get("fee_quote", 0),
            "cash_quote": round(state["cash_quote"], 8),
            "equity_quote": round(equity, 8),
            "realized_pnl_quote": round(result.get("realized_pnl_quote", 0), 8),
            "reason": result["reason"],
        })
    save_state(state)

def main():
    print("OKX BTC SPOT PAPER BOT — public candles only; no authentication; no order endpoints.")
    print("Accounting uses quote units (BTC-USDT prices); these are NOT exact EUR values.")
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
