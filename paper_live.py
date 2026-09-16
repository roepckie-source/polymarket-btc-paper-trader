"""
POLYMARKET BTC 5-MIN PAPER TRADER

PAPER ONLY
NO API KEYS
NO WALLET
NO PRIVATE KEYS
NO REAL ORDERS
NO REAL MONEY

This module:
- reads BTC market data
- reads Polymarket 5-minute market data
- evaluates the existing strategy
- opens paper trades
- stores open trades in CSV
- resolves completed trades
- calculates P&L
- maintains a paper bankroll
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

from market_data import get_market_data as get_btc_market_data
from polymarket_data import get_market_data as get_polymarket_market_data
from strategy import evaluate


# ============================================================
# CONFIG
# ============================================================

PAPER_BANKROLL = 100.00

TRADES_FILE = "paper_trades.csv"
STATE_FILE = "paper_state.csv"

EXPECTED_BTC_SOURCE = "Kraken 5m candle + Coinbase ticker"


# ============================================================
# SAFETY
# ============================================================

print("=" * 70)
print("POLYMARKET BTC 5-MIN PAPER TRADER")
print("=" * 70)
print()
print("PAPER ONLY")
print("NO API KEYS")
print("NO WALLET")
print("NO PRIVATE KEYS")
print("NO REAL ORDERS")
print("NO REAL MONEY")
print()


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_bankroll() -> float:
    """
    Load the current paper bankroll.

    If no state exists yet, start with PAPER_BANKROLL.
    """

    if not os.path.exists(STATE_FILE):
        return PAPER_BANKROLL

    try:
        with open(STATE_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return PAPER_BANKROLL

        return float(rows[-1]["bankroll"])

    except Exception as exc:
        print(f"WARNING: Could not load bankroll: {exc}")
        return PAPER_BANKROLL


def save_bankroll(bankroll: float) -> None:
    """
    Save current paper bankroll.
    """

    with open(STATE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "bankroll"],
        )

        writer.writeheader()

        writer.writerow(
            {
                "timestamp": utc_now(),
                "bankroll": f"{bankroll:.8f}",
            }
        )


def load_open_trade():
    """
    Return the currently open paper trade.

    Only one position is allowed.
    """

    if not os.path.exists(TRADES_FILE):
        return None

    try:
        with open(TRADES_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in reversed(rows):
            if row.get("status") == "OPEN":
                return row

    except Exception as exc:
        print(f"WARNING: Could not read trade file: {exc}")

    return None


def append_trade(row: dict) -> None:
    """
    Append a trade to the CSV ledger.
    """

    fieldnames = [
        "trade_id",
        "status",
        "opened_at",
        "closed_at",
        "window_start",
        "window_end",
        "side",
        "btc_open",
        "btc_entry",
        "btc_close",
        "btc_move_pct",
        "market_price",
        "contracts",
        "position_size",
        "probability",
        "edge",
        "kelly_fraction",
        "pnl",
        "bankroll_after",
        "reason",
    ]

    file_exists = os.path.exists(TRADES_FILE)

    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def rewrite_trades(rows: list[dict]) -> None:
    """
    Rewrite the complete trade ledger.
    Used when an OPEN trade becomes CLOSED.
    """

    fieldnames = [
        "trade_id",
        "status",
        "opened_at",
        "closed_at",
        "window_start",
        "window_end",
        "side",
        "btc_open",
        "btc_entry",
        "btc_close",
        "btc_move_pct",
        "market_price",
        "contracts",
        "position_size",
        "probability",
        "edge",
        "kelly_fraction",
        "pnl",
        "bankroll_after",
        "reason",
    ]

    with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def next_trade_id() -> int:
    """
    Generate the next numeric trade ID.
    """

    if not os.path.exists(TRADES_FILE):
        return 1

    try:
        with open(TRADES_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        ids = []

        for row in rows:
            try:
                ids.append(int(row["trade_id"]))
            except Exception:
                pass

        return max(ids, default=0) + 1

    except Exception:
        return 1


# ============================================================
# RESOLVE OPEN TRADE
# ============================================================

def resolve_open_trade(open_trade: dict, btc: dict, bankroll: float) -> float:
    """
    Resolve the previous 5-minute paper trade.

    The new BTC candle provides the starting price of the
    new window, which is used as the approximate closing
    price of the previous window.

    Payout:
        winning UP/DOWN contract = $1.00
        losing contract = $0.00

    P&L:
        WIN  = contracts * (1 - entry_price)
        LOSS = -position_size
    """

    print("=" * 70)
    print("RESOLVING OPEN PAPER TRADE")
    print("=" * 70)

    trade_window = open_trade["window_start"]
    current_window = str(btc["window_start"])

    if trade_window == current_window:
        print("Current window is still the trade window.")
        print("Trade remains OPEN.")
        print()
        return bankroll

    side = open_trade["side"]

    btc_open = float(open_trade["btc_open"])
    btc_close = float(btc["btc_entry"])

    # The BTC value at the beginning of the new 5m candle
    # is used as the close of the previous 5m candle.
    btc_close = float(btc["btc_open"])

    move_pct = ((btc_close - btc_open) / btc_open) * 100.0

    if move_pct > 0:
        winning_side = "UP"
    else:
        winning_side = "DOWN"

    contracts = float(open_trade["contracts"])
    position_size = float(open_trade["position_size"])
    market_price = float(open_trade["market_price"])

    won = side == winning_side

    if won:
        payout = contracts * 1.00
        pnl = payout - position_size
        result = "WIN"
    else:
        payout = 0.00
        pnl = -position_size
        result = "LOSS"

    new_bankroll = bankroll + pnl

    print(f"Trade ID:       {open_trade['trade_id']}")
    print(f"Side:           {side}")
    print(f"BTC Open:       ${btc_open:,.2f}")
    print(f"BTC Close:      ${btc_close:,.2f}")
    print(f"BTC Move:       {move_pct:+.4f}%")
    print(f"Entry Price:    ${market_price:.4f}")
    print(f"Contracts:      {contracts:.4f}")
    print(f"Position Size:  ${position_size:.2f}")
    print()
    print(f"RESULT:         {result}")
    print(f"P&L:            ${pnl:+.2f}")
    print(f"Bankroll:       ${new_bankroll:.2f}")
    print()

    # Rewrite trade ledger with CLOSED trade
    with open(TRADES_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        if row["trade_id"] == open_trade["trade_id"]:
            row["status"] = result
            row["closed_at"] = utc_now()
            row["btc_close"] = f"{btc_close:.8f}"
            row["btc_move_pct"] = f"{move_pct:.8f}"
            row["pnl"] = f"{pnl:.8f}"
            row["bankroll_after"] = f"{new_bankroll:.8f}"
            row["reason"] = (
                f"{result}: winning side was {winning_side}"
            )

    rewrite_trades(rows)
    save_bankroll(new_bankroll)

    print("Trade successfully closed.")
    print()

    return new_bankroll


# ============================================================
# OPEN PAPER TRADE
# ============================================================

def open_paper_trade(
    btc: dict,
    poly: dict,
    result,
    bankroll: float,
) -> None:
    """
    Open a new paper trade.
    """

    side = result.side

    if side not in ("UP", "DOWN"):
        print("Invalid side. No trade opened.")
        return

    market_price = float(result.market_price)

    btc_open = float(btc["btc_open"])
    btc_current = float(btc["btc_current"])

    movement_pct = (
        (btc_current - btc_open) / btc_open
    ) * 100.0

    position_size = float(result.position_size)

    if position_size > bankroll:
        position_size = bankroll

    contracts = position_size / market_price

    trade_id = next_trade_id()

    print("=" * 70)
    print("PAPER TRADE OPENED")
    print("=" * 70)

    print(f"Trade ID:       {trade_id}")
    print(f"Side:           {side}")
    print(f"BTC Open:       ${btc_open:,.2f}")
    print(f"BTC Entry:      ${btc_current:,.2f}")
    print(f"BTC Move:       {movement_pct:+.4f}%")
    print(f"Market Price:   ${market_price:.4f}")
    print(f"Probability:    {result.probability:.2%}")
    print(f"Edge:           {result.edge:.2%}")
    print(f"Kelly:          {result.kelly_fraction:.2%}")
    print(f"Position Size:  ${position_size:.2f}")
    print(f"Contracts:      {contracts:.4f}")
    print(f"Bankroll:       ${bankroll:.2f}")
    print()
    print("NO REAL ORDER WAS SENT.")
    print()

    append_trade(
        {
            "trade_id": trade_id,
            "status": "OPEN",
            "opened_at": utc_now(),
            "closed_at": "",
            "window_start": str(btc["window_start"]),
            "window_end": str(btc["window_end"]),
            "side": side,
            "btc_open": f"{btc_open:.8f}",
            "btc_entry": f"{btc_current:.8f}",
            "btc_close": "",
            "btc_move_pct": "",
            "market_price": f"{market_price:.8f}",
            "contracts": f"{contracts:.8f}",
            "position_size": f"{position_size:.8f}",
            "probability": f"{result.probability:.8f}",
            "edge": f"{result.edge:.8f}",
            "kelly_fraction": f"{result.kelly_fraction:.8f}",
            "pnl": "",
            "bankroll_after": "",
            "reason": result.reason,
        }
    )

    print(f"Saved to {TRADES_FILE}")
    print()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    bankroll = load_bankroll()

    print(f"Current PAPER BANKROLL: ${bankroll:.2f}")
    print()

    # --------------------------------------------------------
    # BTC DATA
    # --------------------------------------------------------

    print("Loading BTC market data...")

    btc = get_btc_market_data()

    print(f"BTC Open:        ${float(btc['btc_open']):,.2f}")
    print(f"BTC Current:     ${float(btc['btc_current']):,.2f}")
    print(f"BTC Movement:    {float(btc['movement_percent']):+.4f}%")
    print(f"Seconds Left:    {btc['seconds_remaining']}")
    print(f"Source:          {btc['source']}")
    print(f"Window Start:    {btc['window_start']}")
    print(f"Window End:      {btc['window_end']}")
    print()

    if btc["source"] != EXPECTED_BTC_SOURCE:
        raise RuntimeError(
            f"Unexpected BTC data source: {btc['source']}"
        )

    # --------------------------------------------------------
    # CHECK OPEN TRADE
    # --------------------------------------------------------

    open_trade = load_open_trade()

    if open_trade is not None:
        print("OPEN PAPER TRADE FOUND")
        print(f"Trade ID: {open_trade['trade_id']}")
        print(f"Side:     {open_trade['side']}")
        print(
            f"Window:   {open_trade['window_start']}"
        )
        print()

        bankroll = resolve_open_trade(
            open_trade,
            btc,
            bankroll,
        )

        # After resolving, continue evaluating the current
        # market. This allows a new trade in the new window.
        open_trade = load_open_trade()

    # --------------------------------------------------------
    # POLYMARKET DATA
    # --------------------------------------------------------

    print("Loading Polymarket market data...")

    poly = get_polymarket_market_data()

    print(f"Question:        {poly['question']}")
    print(f"Market:          {poly['market_slug']}")
    print(f"Seconds Left:    {poly['seconds_remaining']}")
    print(
        f"UP Price:        {poly['outcome_prices'].get('UP')}"
    )
    print(
        f"DOWN Price:      {poly['outcome_prices'].get('DOWN')}"
    )
    print()

    # --------------------------------------------------------
    # ONE POSITION PROTECTION
    # --------------------------------------------------------

    if open_trade is not None:
        print("OPEN POSITION STILL EXISTS.")
        print("No second paper trade allowed.")
        print()
        print("=" * 70)
        print("RUN COMPLETE")
        print("=" * 70)
        return

    # --------------------------------------------------------
    # DETERMINE SIDE
    # --------------------------------------------------------

    movement_pct = float(btc["movement_percent"])

    if movement_pct > 0:
        side = "UP"
    else:
        side = "DOWN"

    market_price = poly["outcome_prices"].get(side)

    if market_price is None:
        print(f"No {side} market price available.")
        return

    market_price = float(market_price)

    # Use the stricter remaining time.
    seconds_remaining = min(
        int(btc["seconds_remaining"]),
        int(poly["seconds_remaining"]),
    )

    print("STRATEGY INPUT")
    print(f"Direction:       {side}")
    print(f"Market Price:    ${market_price:.4f}")
    print(f"Seconds Left:    {seconds_remaining}")
    print(f"Bankroll:        ${bankroll:.2f}")
    print()

    # --------------------------------------------------------
    # STRATEGY
    # --------------------------------------------------------

    result = evaluate(
        btc_open=float(btc["btc_open"]),
        btc_current=float(btc["btc_current"]),
        market_price=market_price,
        seconds_remaining=seconds_remaining,
        bankroll=bankroll,
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print("=" * 70)
    print("STRATEGY RESULT")
    print("=" * 70)

    print(f"Signal:          {result.signal}")
    print(f"Side:            {result.side}")
    print(f"Probability:     {result.probability:.2%}")
    print(f"Market Price:    ${result.market_price:.4f}")
    print(f"Edge:            {result.edge:.2%}")
    print(f"Kelly:           {result.kelly_fraction:.2%}")
    print(f"Position Size:   ${result.position_size:.2f}")
    print(f"Reason:          {result.reason}")
    print()

    # --------------------------------------------------------
    # OPEN TRADE IF VALID
    # --------------------------------------------------------

    if result.signal == "YES":

        open_paper_trade(
            btc=btc,
            poly=poly,
            result=result,
            bankroll=bankroll,
        )

    else:

        print("NO PAPER TRADE")
        print(f"Reason: {result.reason}")
        print()

    print("=" * 70)
    print("RUN COMPLETE")
    print("=" * 70)
    print()
    print("PAPER ONLY - NO REAL TRADING")
    print()


if __name__ == "__main__":
    main()
