
"""BTC SMA-200 spot backtest. Public market data only; no live orders."""
import argparse
import csv
import json
import math
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

API = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
HEADERS = {"User-Agent": "btc-sma200-paper-backtest/1.0"}


def fetch_daily_candles(years=7, timeout=20):
    if not 2 <= years <= 15:
        raise ValueError("years must be between 2 and 15")

    end = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cursor = end - timedelta(days=365 * years)
    rows = {}

    with requests.Session() as session:
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=299), end)
            response = session.get(
                API,
                params={
                    "granularity": 86400,
                    "start": cursor.isoformat(),
                    "end": chunk_end.isoformat(),
                },
                headers=HEADERS,
                timeout=timeout,
            )
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list):
                raise RuntimeError("Unexpected Coinbase response")

            for candle in data:
                if not isinstance(candle, list) or len(candle) < 6:
                    continue
                ts = int(candle[0])
                row = {
                    "timestamp": ts,
                    "low": float(candle[1]),
                    "high": float(candle[2]),
                    "open": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                }
                if (
                    all(math.isfinite(row[k]) for k in ("open", "close"))
                    and row["open"] > 0
                    and row["close"] > 0
                ):
                    rows[ts] = row

            cursor = chunk_end
            time.sleep(0.15)

    result = [rows[k] for k in sorted(rows)]
    today_start = int(end.timestamp())
    result = [r for r in result if r["timestamp"] < today_start]

    if len(result) < 220:
        raise RuntimeError(
            f"Only {len(result)} daily candles received; need at least 220"
        )
    return result


def load_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                raw_ts = row["timestamp"]
                if raw_ts.isdigit():
                    ts = int(raw_ts)
                else:
                    ts = int(
                        datetime.fromisoformat(
                            raw_ts.replace("Z", "+00:00")
                        ).timestamp()
                    )
                opening, close = float(row["open"]), float(row["close"])
                if (
                    opening > 0 and close > 0
                    and math.isfinite(opening)
                    and math.isfinite(close)
                ):
                    rows.append({
                        "timestamp": ts,
                        "open": opening,
                        "close": close,
                        "low": float(row.get("low") or min(opening, close)),
                        "high": float(row.get("high") or max(opening, close)),
                        "volume": float(row.get("volume") or 0),
                    })
            except (ValueError, KeyError):
                continue

    rows.sort(key=lambda r: r["timestamp"])
    if len(rows) < 220:
        raise ValueError(
            "CSV needs at least 220 daily rows and timestamp,open,close columns"
        )
    return rows


def backtest(
    candles,
    initial_cash=1000.0,
    fee_rate=0.001,
    slippage_rate=0.0005,
):
    if initial_cash <= 0 or fee_rate < 0 or slippage_rate < 0:
        raise ValueError("Cash must be positive; costs cannot be negative")

    candles = sorted(candles, key=lambda r: r["timestamp"])
    if len(candles) < 220:
        raise ValueError("Need at least 220 daily candles")

    closes = [float(c["close"]) for c in candles]
    if any(not math.isfinite(x) or x <= 0 for x in closes):
        raise ValueError("Closing prices must be finite and positive")

    sma = [None] * len(candles)
    running = 0.0
    for i, price in enumerate(closes):
        running += price
        if i >= 200:
            running -= closes[i - 200]
        if i >= 199:
            sma[i] = running / 200

    cash, btc = initial_cash, 0.0
    in_market = False
    trades, curve = [], []
    peak, max_drawdown = initial_cash, 0.0
    fee_costs = slippage_costs = 0.0
    cost_rate = fee_rate + slippage_rate

    for i, candle in enumerate(candles):
        # Yesterday's completed close gives today's opening execution.
        if i >= 2 and sma[i - 1] is not None and sma[i - 2] is not None:
            previous_above = closes[i - 2] > sma[i - 2]
            yesterday_above = closes[i - 1] > sma[i - 1]
            previous_below = closes[i - 2] < sma[i - 2]
            yesterday_below = closes[i - 1] < sma[i - 1]
            buy_signal = not previous_above and yesterday_above
            sell_signal = not previous_below and yesterday_below
            price = float(candle["open"])
            date = datetime.fromtimestamp(
                candle["timestamp"], timezone.utc
            ).date().isoformat()

            if buy_signal and not in_market:
                spend = cash / (1 + cost_rate)
                fee = spend * fee_rate
                slippage = spend * slippage_rate
                btc = spend / price
                cash = 0.0
                in_market = True
                fee_costs += fee
                slippage_costs += slippage
                trades.append({
                    "timestamp": candle["timestamp"],
                    "date": date,
                    "action": "BUY",
                    "price": price,
                    "btc": btc,
                    "fee": fee,
                    "slippage": slippage,
                })

            elif sell_signal and in_market:
                gross = btc * price
                fee = gross * fee_rate
                slippage = gross * slippage_rate
                cash = gross * (1 - cost_rate)
                fee_costs += fee
                slippage_costs += slippage
                trades.append({
                    "timestamp": candle["timestamp"],
                    "date": date,
                    "action": "SELL",
                    "price": price,
                    "btc": btc,
                    "fee": fee,
                    "slippage": slippage,
                })
                btc = 0.0
                in_market = False

        equity = cash + btc * closes[i]
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        curve.append({
            "timestamp": candle["timestamp"],
            "date": datetime.fromtimestamp(
                candle["timestamp"], timezone.utc
            ).date().isoformat(),
            "close": closes[i],
            "sma200": sma[i],
            "equity": equity,
            "buy_hold_equity": initial_cash * closes[i] / closes[0],
            "in_market": int(in_market),
        })

    final_equity = curve[-1]["equity"]
    buy_hold = curve[-1]["buy_hold_equity"]
    years = max(
        1 / 365.25,
        (candles[-1]["timestamp"] - candles[0]["timestamp"]) / 86400 / 365.25,
    )

    summary = {
        "start_date": curve[0]["date"],
        "end_date": curve[-1]["date"],
        "candles": len(candles),
        "initial_cash": round(initial_cash, 2),
        "ending_equity": round(final_equity, 2),
        "strategy_return_pct": round((final_equity / initial_cash - 1) * 100, 2),
        "buy_hold_ending_equity": round(buy_hold, 2),
        "buy_hold_return_pct": round((buy_hold / initial_cash - 1) * 100, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "completed_trades": sum(t["action"] == "SELL" for t in trades),
        "entries": sum(t["action"] == "BUY" for t in trades),
        "fees_estimated": round(fee_costs, 2),
        "slippage_estimated": round(slippage_costs, 2),
        "annualized_return_pct_approx": round(
            ((final_equity / initial_cash) ** (1 / years) - 1) * 100, 2
        ) if final_equity > 0 else None,
        "note": (
            "Daily SMA200; long-only spot; signal after daily close, "
            "execute at next candle open. Not a profit guarantee."
        ),
    }
    return trades, summary, curve


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="BTC SMA200 spot backtest; no live trading"
    )
    parser.add_argument("--csv", help="Optional daily candle CSV")
    parser.add_argument("--years", type=int, default=7)
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--slippage-rate", type=float, default=0.0005)
    parser.add_argument("--output-dir", default="sma200-results")
    args = parser.parse_args()

    candles = load_csv(args.csv) if args.csv else fetch_daily_candles(args.years)
    trades, summary, curve = backtest(
        candles, args.initial_cash, args.fee_rate, args.slippage_rate
    )

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "equity_curve.csv", curve)
    write_csv(output / "trades.csv", trades)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"Saved results to {output.resolve()}")


if __name__ == "__main__":
    main()
