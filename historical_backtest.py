"""CSV-driven historical backtest for the BTC 5-minute paper strategy.

This tool is offline and paper-only. It never places orders or calls an exchange.
Required input columns:
  timestamp, btc_open, btc_current, seconds_remaining, up_price, outcome
Optional columns:
  down_price, fee_rate, slippage_per_contract
outcome must be the resolved market outcome: UP or DOWN. Do not use unresolved rows.

Example:
  python historical_backtest.py historical_btc_5m.csv --output backtest_results.csv
"""
from __future__ import annotations
import argparse
import csv
import math
from pathlib import Path
from typing import Any

import strategy

REQUIRED = {"timestamp", "btc_open", "btc_current", "seconds_remaining", "up_price", "outcome"}


def _number(row: dict[str, str], key: str, default: float | None = None) -> float:
    raw = row.get(key, "")
    if raw in (None, ""):
        if default is None:
            raise ValueError(f"Missing required numeric value: {key}")
        return default
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"Non-finite value for {key}")
    return value


def load_rows(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED - fields
        if missing:
            raise ValueError("CSV missing required columns: " + ", ".join(sorted(missing)))
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]
    if not rows:
        raise ValueError("Input CSV has no data rows")
    return rows


def run_backtest(rows: list[dict[str, str]], bankroll: float = 100.0,
                 fee_rate: float = 0.0, slippage_per_contract: float = 0.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run current strategy on resolved historical snapshots and return trades + summary.

    fee_rate is a fraction of entry notional (e.g. 0.01 = 1%).
    slippage_per_contract is a dollar cost per contract. Set values from the venue's
    actual fee schedule and measured execution data; defaults are zero and optimistic.
    """
    if bankroll <= 0 or fee_rate < 0 or slippage_per_contract < 0:
        raise ValueError("bankroll must be positive; costs cannot be negative")
    cash = bankroll
    results: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    wins = losses = 0
    gross_pnl = fees_total = slippage_total = 0.0
    peak = bankroll
    max_drawdown = 0.0

    for row in rows:
        outcome = (row.get("outcome") or "").strip().upper()
        if outcome not in {"UP", "DOWN"}:
            raise ValueError(f"Invalid outcome {outcome!r}; use UP or DOWN only")
        up_price = _number(row, "up_price")
        side = "UP" if up_price >= 0.5 else "DOWN"
        market_price = up_price if side == "UP" else _number(row, "down_price", 1.0 - up_price)
        result = strategy.evaluate(
            btc_open=_number(row, "btc_open"),
            btc_current=_number(row, "btc_current"),
            seconds_remaining=int(_number(row, "seconds_remaining")),
            market_price=market_price,
            bankroll=cash,
        )
        reasons[result.reason] = reasons.get(result.reason, 0) + 1
        item: dict[str, Any] = {
            "timestamp": row["timestamp"], "outcome": outcome,
            "signal": bool(result.signal), "side": result.side,
            "probability": result.probability, "market_price": result.market_price,
            "edge": result.edge, "position_usd": 0.0, "contracts": 0.0,
            "fee_usd": 0.0, "slippage_usd": 0.0, "pnl_usd": 0.0,
            "bankroll_after": cash, "reason": result.reason,
        }
        if result.signal and result.position_size > 0 and 0 < result.market_price < 1:
            stake = min(result.position_size, cash)
            contracts = stake / result.market_price
            fees = stake * fee_rate
            slippage = contracts * slippage_per_contract
            won = result.side == outcome
            payout = contracts if won else 0.0
            pnl = payout - stake - fees - slippage
            cash += pnl
            gross_pnl += payout - stake
            fees_total += fees
            slippage_total += slippage
            wins += int(won)
            losses += int(not won)
            item.update({"position_usd": stake, "contracts": contracts, "fee_usd": fees,
                         "slippage_usd": slippage, "pnl_usd": pnl, "bankroll_after": cash,
                         "reason": "RESOLVED_WIN" if won else "RESOLVED_LOSS"})
            peak = max(peak, cash)
            max_drawdown = max(max_drawdown, (peak - cash) / peak if peak else 0.0)
        results.append(item)

    trades = wins + losses
    summary = {
        "rows": len(rows), "trades": trades, "no_trade_rows": len(rows) - trades,
        "wins": wins, "losses": losses, "win_rate": wins / trades if trades else None,
        "starting_bankroll": bankroll, "ending_bankroll": cash,
        "net_pnl": cash - bankroll, "gross_pnl_before_costs": gross_pnl,
        "fees": fees_total, "slippage": slippage_total,
        "max_drawdown_pct": max_drawdown * 100.0,
        "rejection_reasons": reasons,
        "warning": "If fee/slippage inputs are zero, results are optimistic. This is not evidence of future profitability.",
    }
    return results, summary


def write_results(path: str | Path, results: list[dict[str, Any]]) -> None:
    if not results:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Historical resolved market CSV")
    parser.add_argument("--output", default="historical_backtest_results.csv")
    parser.add_argument("--bankroll", type=float, default=100.0)
    parser.add_argument("--fee-rate", type=float, default=0.0, help="Fraction of entry notional, e.g. 0.01")
    parser.add_argument("--slippage-per-contract", type=float, default=0.0, help="USD cost per contract")
    args = parser.parse_args()
    try:
        rows = load_rows(args.csv)
        results, summary = run_backtest(rows, args.bankroll, args.fee_rate, args.slippage_per_contract)
        write_results(args.output, results)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print("HISTORICAL PAPER BACKTEST — NO ORDERS PLACED")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"trade_details_csv: {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
