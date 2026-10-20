"""Cross-market Polymarket-signal paper trader.

READ-ONLY DATA + SIMULATED EXECUTION ONLY. This module has no order API,
credentials, wallet, or private-key support.

It compares (1) a Polymarket UP/DOWN-probability signal traded as a simulated
BTC long/short derivative, (2) the same signal as spot-long-only, and (3) a
simple BTC momentum baseline. Exchange fees and slippage are configurable
assumptions, not guaranteed fee quotes.
"""
from __future__ import annotations
import argparse
import csv
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import market_data
import polymarket_data

DEFAULT_OUTPUT = "cross_market_paper.csv"

@dataclass(frozen=True)
class Config:
    up_threshold: float = 0.60
    down_threshold: float = 0.40
    fee_bps: float = 40.0       # illustrative round-trip fee budget, bps
    slippage_bps: float = 10.0  # illustrative round-trip slippage budget, bps
    position_usd: float = 100.0
    poll_seconds: int = 10


def infer_poly_signal(outcome_prices: dict, config: Config = Config()) -> str:
    """Return UP, DOWN, or FLAT from public outcome prices."""
    normalized = {str(k).strip().upper(): float(v) for k, v in outcome_prices.items()}
    up = normalized.get("UP")
    down = normalized.get("DOWN")
    if up is None or down is None or not (0 <= up <= 1 and 0 <= down <= 1):
        return "FLAT"
    if up >= config.up_threshold and up > down:
        return "UP"
    if down >= (1.0 - config.down_threshold) and down > up:
        return "DOWN"
    return "FLAT"


def net_pnl_usd(entry: float, exit: float, side: str, notional: float,
                fee_bps: float, slippage_bps: float) -> float:
    """Directional paper P&L with simple round-trip cost haircut."""
    if entry <= 0 or exit <= 0 or notional < 0:
        raise ValueError("Prices must be positive and notional non-negative")
    if side not in {"LONG", "SHORT", "FLAT"}:
        raise ValueError("side must be LONG, SHORT, or FLAT")
    if side == "FLAT" or notional == 0:
        return 0.0
    gross = notional * ((exit - entry) / entry) * (1 if side == "LONG" else -1)
    costs = notional * (fee_bps + slippage_bps) / 10_000.0
    return gross - costs


def _append_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def collect_once(output: str = DEFAULT_OUTPUT, config: Config = Config()) -> dict:
    """Fetch public observations and append signals. Does not place orders."""
    poly = polymarket_data.get_market_data()
    btc = market_data.get_market_data()
    signal = infer_poly_signal(poly.get("outcome_prices", {}), config)
    momentum_side = "LONG" if btc["movement_percent"] > 0 else "SHORT" if btc["movement_percent"] < 0 else "FLAT"
    poly_side = {"UP": "LONG", "DOWN": "SHORT", "FLAT": "FLAT"}[signal]
    # Observation log only. P&L is calculated only after a later close price is known.
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "market_slug": poly.get("market_slug", ""),
        "window_start": poly.get("window_start", ""),
        "seconds_remaining": poly.get("seconds_remaining", ""),
        "polymarket_up": poly.get("outcome_prices", {}).get("UP", ""),
        "polymarket_down": poly.get("outcome_prices", {}).get("DOWN", ""),
        "btc_open": btc.get("btc_open", ""),
        "btc_current": btc.get("btc_current", ""),
        "btc_movement_pct": btc.get("movement_percent", ""),
        "poly_signal": signal,
        "poly_signal_derivative_paper_side": poly_side,
        "poly_signal_spot_paper_side": "LONG" if signal == "UP" else "FLAT",
        "momentum_baseline_paper_side": momentum_side,
        "execution": "PAPER_ONLY_NO_ORDERS",
    }
    _append_row(Path(output), row)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Polymarket signal + BTC paper monitor")
    parser.add_argument("--once", action="store_true", help="collect one observation and exit")
    parser.add_argument("--interval", type=int, default=10, help="poll interval seconds (minimum 5)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="CSV output path")
    args = parser.parse_args()
    interval = max(5, args.interval)
    print("PAPER ONLY | PUBLIC DATA ONLY | NO ORDERS | NO KEYS | NO WALLET")
    while True:
        try:
            row = collect_once(args.output)
            print(f"{row['timestamp_utc']} signal={row['poly_signal']} "
                  f"BTC={row['btc_current']} move={row['btc_movement_pct']:.4f}% "
                  f"remaining={row['seconds_remaining']}s")
        except Exception as exc:
            print(f"Observation failed: {type(exc).__name__}: {exc}")
        if args.once:
            break
        time.sleep(interval)

if __name__ == "__main__":
    main()
