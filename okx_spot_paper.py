
"""Persistent BTC 5-minute spot paper trader.
Paper trading only. No real order code or API credentials.
"""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from okx_market_data import fetch_candles
from okx_paper_config import (
    STARTING_EQUITY_QUOTE,
    MAX_RISK_QUOTE,
    MAX_POSITION_QUOTE,
    FEE_RATE,
    INSTRUMENT,
    BAR,
    CANDLE_LIMIT,
    STOP_DISTANCE,
)

STATE_PATH = Path(os.getenv("PAPER_STATE_PATH", "okx_paper_state.json"))
TRADES_PATH = Path(os.getenv("PAPER_TRADES_PATH", "okx_paper_trades.csv"))

FIELDS = [
    "time_utc",
    "candle_ts",
    "action",
    "price_usdt",
    "btc",
    "notional_usdt",
    "fee_usdt",
    "cash_usdt",
    "equity_usdt",
    "realized_pnl_usdt",
    "reason",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def ema(values, period):
    if not values:
        return []

    alpha = 2.0 / (period + 1)
    result = [float(values[0])]

    for value in values[1:]:
        result.append(
            alpha * float(value) + (1 - alpha) * result[-1]
        )

    return result


def make_signal(candles):
    """Evaluate confirmed candles only."""
    if len(candles) < 22:
        return "HOLD", "not enough confirmed candles"

    closes = [float(c["close"]) for c in candles]
    averages = ema(closes, 21)

    if (
        closes[-1] > averages[-1]
        and closes[-1] > closes[-2] > closes[-3] > closes[-4]
    ):
        return "BUY", "close above EMA21 and three rising closes"

    if closes[-1] < averages[-1]:
        return "SELL", "close below EMA21"

    return "HOLD", "no entry/exit condition"


def initial_state():
    return {
        "cash_usdt": float(STARTING_EQUITY_QUOTE),
        "btc": 0.0,
        "entry_price": None,
        "entry_fee_usdt": 0.0,
        "stop_price": None,
        "last_candle_ts": None,
        "equity_peak_usdt": float(STARTING_EQUITY_QUOTE),
        "halted": False,
        "updated_at_utc": None,
    }


def load_state():
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))

            if "cash_usdt" in data and "btc" in data:
                # Preserve the existing paper account across runs.
                return data

        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: Could not read state file: {exc}")

    print("WARNING: Initializing a new paper account.")
    return initial_state()


def save_state(state):
    """Atomically save the current paper account."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    state["updated_at_utc"] = utc_now()

    temp_path = STATE_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(STATE_PATH)


def ensure_trade_log():
    """Create the CSV header even before the first trade."""
    TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not TRADES_PATH.exists() or TRADES_PATH.stat().st_size == 0:
        with TRADES_PATH.open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()


def append_trade(row):
    """Append one simulated BUY or SELL to the trade history."""
    ensure_trade_log()

    with TRADES_PATH.open(
        "a", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writerow({key: row.get(key, "") for key in FIELDS})


def equity(state, price):
    return (
        float(state["cash_usdt"])
        + float(state["btc"]) * float(price)
    )


def step(
    state,
    candles,
    fee_rate=FEE_RATE,
    max_risk=MAX_RISK_QUOTE,
    max_position=MAX_POSITION_QUOTE,
    stop_distance=STOP_DISTANCE,
):
    """Process one new candle using simulated spot orders only."""
    if not candles:
        raise ValueError("No confirmed candles received")

    if not 0 <= fee_rate < 1:
        raise ValueError("fee_rate must be between 0 and 1")

    if not 0 < stop_distance < 1:
        raise ValueError("stop_distance must be between 0 and 1")

    candle = candles[-1]
    price = float(candle["close"])
    candle_ts = int(candle["ts"])

    if price <= 0:
        raise ValueError("Candle price must be positive")

    if state.get("last_candle_ts") == candle_ts:
        return state, {
            "action": "NONE",
            "reason": "already processed this candle",
        }

    state["last_candle_ts"] = candle_ts

    signal, reason = make_signal(candles)
    current_equity = equity(state, price)

    state["equity_peak_usdt"] = max(
        float(state.get("equity_peak_usdt", current_equity)),
        current_equity,
    )

    if state.get("halted"):
        return state, {
            "action": "HALTED",
            "reason": "risk halt is active",
        }

    # Exit an existing simulated BTC spot position.
    if float(state["btc"]) > 0:
        stop_price = state.get("stop_price")

        stop_hit = (
            stop_price is not None and price <= float(stop_price)
        )

        if stop_hit or signal == "SELL":
            quantity = float(state["btc"])
            gross = quantity * price
            exit_fee = gross * fee_rate

            entry_cost = quantity * float(state["entry_price"])
            entry_fee = float(state.get("entry_fee_usdt", 0.0))

            realized_pnl = (
                gross - exit_fee - entry_cost - entry_fee
            )

            state["cash_usdt"] += gross - exit_fee

            state.update({
                "btc": 0.0,
                "entry_price": None,
                "entry_fee_usdt": 0.0,
                "stop_price": None,
            })

            if realized_pnl < -max_risk:
                state["halted"] = True
                reason += (
                    "; risk threshold exceeded; "
                    "loss can exceed target due to gaps, fees or slippage"
                )

            return state, {
                "action": "SELL",
                "reason": (
                    "simulated stop triggered"
                    if stop_hit
                    else reason
                ),
                "price": price,
                "btc": quantity,
                "notional_usdt": gross,
                "fee_usdt": exit_fee,
                "realized_pnl_usdt": realized_pnl,
            }

        return state, {
            "action": "NONE",
            "reason": "position open; waiting for exit or stop",
        }

    if signal != "BUY":
        return state, {
            "action": "NONE",
            "reason": reason,
        }

    # Position size is limited by both configured risk and notional cap.
    notional = min(
        float(max_position),
        float(max_risk) / stop_distance,
        float(state["cash_usdt"]) / (1 + fee_rate),
    )

    if notional <= 0:
        state["halted"] = True
        return state, {
            "action": "HALTED",
            "reason": "insufficient virtual cash",
        }

    quantity = notional / price
    entry_fee = notional * fee_rate

    state["cash_usdt"] -= notional + entry_fee
    state.update({
        "btc": quantity,
        "entry_price": price,
        "entry_fee_usdt": entry_fee,
        "stop_price": price * (1 - stop_distance),
    })

    return state, {
        "action": "BUY",
        "reason": reason,
        "price": price,
        "btc": quantity,
        "notional_usdt": notional,
        "fee_usdt": entry_fee,
        "realized_pnl_usdt": 0.0,
    }


def run_once():
    """Fetch market data, evaluate once, and persist paper state."""
    ensure_trade_log()

    candles = fetch_candles(INSTRUMENT, BAR, CANDLE_LIMIT)

    if not candles:
        raise ValueError("Market data returned no confirmed candles")

    state = load_state()
    state, result = step(state, candles)

    price = float(candles[-1]["close"])
    current_equity = equity(state, price)

    print(
        f"{utc_now()} | {INSTRUMENT} {BAR} "
        f"| close={price:.2f} USDT"
    )
    print(
        f"Action={result['action']} | {result['reason']}"
    )
    print(
        f"Equity={current_equity:.4f} USDT "
        f"| cash={state['cash_usdt']:.4f} USDT "
        f"| BTC={state['btc']:.8f}"
    )

    if result["action"] in ("BUY", "SELL"):
        append_trade({
            "time_utc": utc_now(),
            "candle_ts": candles[-1]["ts"],
            "action": result["action"],
            "price_usdt": result["price"],
            "btc": result["btc"],
            "notional_usdt": result.get("notional_usdt", 0),
            "fee_usdt": result.get("fee_usdt", 0),
            "cash_usdt": round(state["cash_usdt"], 8),
            "equity_usdt": round(current_equity, 8),
            "realized_pnl_usdt": round(
                result.get("realized_pnl_usdt", 0), 8
            ),
            "reason": result["reason"],
        })

    save_state(state)

    return state, result


if __name__ == "__main__":
    run_once()
