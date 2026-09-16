"""
POLYMARKET BTC 5-MIN PAPER TRADER

PAPER ONLY

NO API KEYS
NO WALLET
NO PRIVATE KEYS
NO REAL ORDERS
NO REAL MONEY
"""

import csv
import os
from datetime import datetime, timezone

from strategy import evaluate


# ============================================================
# CONFIG
# ============================================================

PAPER_BANKROLL = 100.00

TRADES_FILE = "paper_trades.csv"
STATE_FILE = "paper_state.csv"

EXPECTED_BTC_SOURCE = "Kraken 5m candle + Coinbase ticker"


# ============================================================
# TIME
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# BANKROLL
# ============================================================

def load_bankroll():
    """
    Load current paper bankroll.

    If no state file exists, start with PAPER_BANKROLL.
    """

    if not os.path.exists(STATE_FILE):
        return PAPER_BANKROLL

    try:
        with open(STATE_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                value = row.get("bankroll")

                if value is not None:
                    return float(value)

    except Exception as e:
        print(f"WARNING: Could not load bankroll: {e}")

    return PAPER_BANKROLL


def save_bankroll(bankroll):
    """
    Save current paper bankroll.
    """

    with open(STATE_FILE, "w", newline="", encoding="utf-8") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "updated_at",
                "bankroll",
            ],
        )

        writer.writeheader()

        writer.writerow(
            {
                "updated_at": utc_now(),
                "bankroll": f"{bankroll:.8f}",
            }
        )


# ============================================================
# OPEN TRADE
# ============================================================

def load_open_trade():
    """
    Return the currently open paper trade.

    Only one open trade is allowed.
    """

    if not os.path.exists(TRADES_FILE):
        return None

    try:
        with open(TRADES_FILE, "r", newline="", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:

                if row.get("status") == "OPEN":
                    return row

    except Exception as e:
        print(f"WARNING: Could not load open trade: {e}")

    return None


# ============================================================
# TRADE STORAGE
# ============================================================

TRADE_FIELDS = [
    "trade_id",
    "status",
    "opened_at",
    "resolved_at",

    "window_start",
    "window_end",

    "side",

    "btc_open",
    "btc_entry",

    "btc_close",

    "market_price",
    "contracts",

    "probability",
    "edge",
    "kelly",

    "position_size",

    "payout",
    "pnl",

    "bankroll_before",
    "bankroll_after",

    "result",
]


def append_trade(trade):
    """
    Append one trade to paper_trades.csv.
    """

    file_exists = os.path.exists(TRADES_FILE)

    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=TRADE_FIELDS,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(trade)


def rewrite_trades(trades):
    """
    Rewrite complete trade history.

    Used when resolving an existing OPEN trade.
    """

    with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=TRADE_FIELDS,
        )

        writer.writeheader()

        for trade in trades:
            writer.writerow(trade)


def next_trade_id():
    """
    Generate next sequential trade ID.
    """

    if not os.path.exists(TRADES_FILE):
        return 1

    highest = 0

    try:
        with open(TRADES_FILE, "r", newline="", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:

                try:
                    trade_id = int(row.get("trade_id", 0))
                    highest = max(highest, trade_id)

                except (ValueError, TypeError):
                    pass

    except Exception:
        pass

    return highest + 1


# ============================================================
# RESOLVE TRADE
# ============================================================

def resolve_open_trade(open_trade, new_market_data, bankroll):
    """
    Resolve the previous 5-minute trade.

    The new 5-minute candle open is used as the approximate
    close of the previous window.
    """

    if open_trade is None:
        return bankroll

    previous_window_start = int(
        float(open_trade["window_start"])
    )

    current_window_start = int(
        float(new_market_data["window_start"])
    )

    # --------------------------------------------------------
    # Same window -> nothing to resolve
    # --------------------------------------------------------

    if current_window_start <= previous_window_start:

        return bankroll

    # --------------------------------------------------------
    # Previous BTC close
    # --------------------------------------------------------

    btc_close = float(
        new_market_data["btc_open"]
    )

    btc_open = float(
        open_trade["btc_open"]
    )

    movement_percent = (
        (btc_close - btc_open)
        / btc_open
        * 100.0
    )

    winning_side = (
        "UP"
        if movement_percent > 0
        else "DOWN"
    )

    trade_side = open_trade["side"]

    position_size = float(
        open_trade["position_size"]
    )

    market_price = float(
        open_trade["market_price"]
    )

    contracts = float(
        open_trade["contracts"]
    )

    # --------------------------------------------------------
    # Resolve WIN / LOSS
    # --------------------------------------------------------

    if trade_side == winning_side:

        payout = contracts
        pnl = payout - position_size
        result = "WIN"

    else:

        payout = 0.0
        pnl = -position_size
        result = "LOSS"

    bankroll_before = bankroll
    bankroll_after = bankroll + pnl

    # --------------------------------------------------------
    # Update trade history
    # --------------------------------------------------------

    trades = []

    if os.path.exists(TRADES_FILE):

        try:

            with open(
                TRADES_FILE,
                "r",
                newline="",
                encoding="utf-8",
            ) as f:

                reader = csv.DictReader(f)

                for row in reader:
                    trades.append(row)

        except Exception as e:

            print(
                f"WARNING: Could not read trade history: {e}"
            )

    resolved = False

    for trade in trades:

        if (
            trade.get("trade_id")
            == open_trade.get("trade_id")
            and trade.get("status") == "OPEN"
        ):

            trade["status"] = result
            trade["resolved_at"] = utc_now()

            trade["btc_close"] = (
                f"{btc_close:.2f}"
            )

            trade["payout"] = (
                f"{payout:.8f}"
            )

            trade["pnl"] = (
                f"{pnl:.8f}"
            )

            trade["bankroll_before"] = (
                f"{bankroll_before:.8f}"
            )

            trade["bankroll_after"] = (
                f"{bankroll_after:.8f}"
            )

            trade["result"] = result

            resolved = True

    if resolved:
        rewrite_trades(trades)

    # --------------------------------------------------------
    # Save bankroll
    # --------------------------------------------------------

    save_bankroll(bankroll_after)

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAPER TRADE RESOLVED")
    print("=" * 70)

    print(f"Trade ID:       {open_trade['trade_id']}")
    print(f"Side:           {trade_side}")

    print(f"BTC Open:       ${btc_open:,.2f}")
    print(f"BTC Close:      ${btc_close:,.2f}")

    print(
        f"BTC Movement:   {movement_percent:+.4f}%"
    )

    print(f"Winning Side:   {winning_side}")
    print(f"Result:         {result}")

    print(
        f"Position:       ${position_size:.2f}"
    )

    print(
        f"Contracts:      {contracts:.4f}"
    )

    print(
        f"Payout:         ${payout:.2f}"
    )

    print(
        f"P&L:            ${pnl:+.2f}"
    )

    print(
        f"Bankroll:       ${bankroll_before:.2f}"
        f" -> ${bankroll_after:.2f}"
    )

    print("=" * 70)
    print()

    return bankroll_after


# ============================================================
# OPEN PAPER TRADE
# ============================================================

def open_paper_trade(
    result,
    btc_data,
    market_data,
    bankroll,
):
    """
    Open a new paper trade.

    This function NEVER submits an order.
    """

    position_size = float(
        result.position_size
    )

    market_price = float(
        result.market_price
    )

    side = result.side

    btc_open = float(
        btc_data["btc_open"]
    )

    btc_current = float(
        btc_data["btc_current"]
    )

    window_start = int(
        btc_data["window_start"]
    )

    window_end = int(
        btc_data["window_end"]
    )

    # --------------------------------------------------------
    # Safety validation
    # --------------------------------------------------------

    if position_size <= 0:
        print(
            "ERROR: Invalid position size."
        )
        return bankroll

    if market_price <= 0:
        print(
            "ERROR: Invalid market price."
        )
        return bankroll

    if side not in ("UP", "DOWN"):
        print(
            "ERROR: Invalid trade side."
        )
        return bankroll

    if position_size > bankroll:
        print(
            "ERROR: Position size exceeds bankroll."
        )
        return bankroll

    # --------------------------------------------------------
    # Calculate contracts
    # --------------------------------------------------------

    contracts = (
        position_size / market_price
    )

    trade_id = next_trade_id()

    # --------------------------------------------------------
    # Create OPEN trade
    # --------------------------------------------------------

    trade = {
        "trade_id": trade_id,
        "status": "OPEN",

        "opened_at": utc_now(),
        "resolved_at": "",

        "window_start": window_start,
        "window_end": window_end,

        "side": side,

        "btc_open": f"{btc_open:.2f}",
        "btc_entry": f"{btc_current:.2f}",

        "btc_close": "",

        "market_price": f"{market_price:.8f}",
        "contracts": f"{contracts:.8f}",

        "probability": (
            f"{float(result.probability):.8f}"
        ),

        "edge": (
            f"{float(result.edge):.8f}"
        ),

        "kelly": (
            f"{float(result.kelly_fraction):.8f}"
        ),

        "position_size": (
            f"{position_size:.8f}"
        ),

        "payout": "",
        "pnl": "",

        "bankroll_before": (
            f"{bankroll:.8f}"
        ),

        "bankroll_after": "",

        "result": "",
    }

    append_trade(trade)

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # The position is reserved in the paper simulation.
    #
    # We do NOT remove it permanently from bankroll here.
    # The final P&L is applied when the trade resolves.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAPER TRADE OPENED")
    print("=" * 70)

    print(f"Trade ID:       {trade_id}")
    print(f"Side:           {side}")

    print(
        f"BTC Open:       ${btc_open:,.2f}"
    )

    print(
        f"BTC Current:    ${btc_current:,.2f}"
    )

    print(
        f"Market Price:   ${market_price:.4f}"
    )

    print(
        f"Probability:    "
        f"{float(result.probability) * 100:.2f}%"
    )

    print(
        f"Edge:           "
        f"{float(result.edge) * 100:.2f}%"
    )

    print(
        f"Kelly:          "
        f"{float(result.kelly_fraction) * 100:.2f}%"
    )

    print(
        f"Position Size:  ${position_size:.2f}"
    )

    print(
        f"Contracts:      {contracts:.4f}"
    )

    print(
        f"Bankroll:       ${bankroll:.2f}"
    )

    print()
    print("STATUS: OPEN")
    print("PAPER ONLY - NO REAL ORDER")
    print("=" * 70)
    print()

    return bankroll


# ============================================================
# MAIN
# ============================================================

def main():

    print()
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

    # --------------------------------------------------------
    # Load bankroll
    # --------------------------------------------------------

    bankroll = load_bankroll()

    print(
        f"Current PAPER BANKROLL: "
        f"${bankroll:.2f}"
    )

    # --------------------------------------------------------
    # Import market data modules
    # --------------------------------------------------------

    try:

        from market_data import get_btc_market_data
        from polymarket_data import get_market_data

    except Exception as e:

        print(
            f"ERROR: Could not import market modules: {e}"
        )

        return

    # --------------------------------------------------------
    # Load BTC data
    # --------------------------------------------------------

    print()
    print("Loading BTC market data...")

    try:

        btc_data = get_btc_market_data()

    except Exception as e:

        print(
            f"ERROR: BTC market data failed: {e}"
        )

        return

    print(
        f"BTC Open:        "
        f"${btc_data['btc_open']:,.2f}"
    )

    print(
        f"BTC Current:     "
        f"${btc_data['btc_current']:,.2f}"
    )

    print(
        f"BTC Movement:    "
        f"{btc_data['movement_percent']:+.4f}%"
    )

    print(
        f"Seconds Left:    "
        f"{btc_data['seconds_remaining']}"
    )

    print(
        f"Source:          "
        f"{btc_data['source']}"
    )

    print(
        f"Window Start:    "
        f"{btc_data['window_start']}"
    )

    print(
        f"Window End:      "
        f"{btc_data['window_end']}"
    )

    # --------------------------------------------------------
    # Safety check data source
    # --------------------------------------------------------

    if btc_data["source"] != EXPECTED_BTC_SOURCE:

        print()
        print(
            "ERROR: Unexpected BTC data source."
        )

        print(
            f"Expected: {EXPECTED_BTC_SOURCE}"
        )

        print(
            f"Actual:   {btc_data['source']}"
        )

        return

    # --------------------------------------------------------
    # Load Polymarket data
    # --------------------------------------------------------

    print()
    print("Loading Polymarket market data...")

    try:

        market_data = get_market_data()

    except Exception as e:

        print(
            f"ERROR: Polymarket market data failed: {e}"
        )

        return

    print(
        f"Question:        "
        f"{market_data['question']}"
    )

    print(
        f"Market:          "
        f"{market_data['market_slug']}"
    )

    print(
        f"Seconds Left:    "
        f"{market_data['seconds_remaining']}"
    )

    # --------------------------------------------------------
    # Prices
    # --------------------------------------------------------

    outcome_prices = market_data.get(
        "outcome_prices",
        {},
    )

    up_price = outcome_prices.get(
        "UP"
    )

    down_price = outcome_prices.get(
        "DOWN"
    )

    if up_price is None or down_price is None:

        print(
            "ERROR: UP/DOWN prices unavailable."
        )

        return

    up_price = float(up_price)
    down_price = float(down_price)

    print(
        f"UP Price:        {up_price:.3f}"
    )

    print(
        f"DOWN Price:      {down_price:.3f}"
    )

    # --------------------------------------------------------
    # Resolve an existing trade FIRST
    # --------------------------------------------------------

    open_trade = load_open_trade()

    if open_trade is not None:

        print()
        print(
            "OPEN PAPER TRADE DETECTED"
        )

        print(
            f"Trade ID: {open_trade['trade_id']}"
        )

        print(
            f"Side:     {open_trade['side']}"
        )

        print(
            f"Window:   {open_trade['window_start']}"
        )

        bankroll = resolve_open_trade(
            open_trade,
            btc_data,
            bankroll,
        )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Check again after resolving.
    #
    # There must NEVER be more than one OPEN trade.
    # --------------------------------------------------------

    open_trade = load_open_trade()

    if open_trade is not None:

        print()
        print(
            "OPEN TRADE STILL ACTIVE"
        )

        print(
            f"Trade ID: {open_trade['trade_id']}"
        )

        print(
            "No new trade will be opened."
        )

        print()
        print(
            "=" * 70
        )

        print(
            "RUN COMPLETE"
        )

        print(
            "=" * 70
        )

        print(
            "PAPER ONLY - NO REAL TRADING"
        )

        return

    # --------------------------------------------------------
    # Determine direction
    # --------------------------------------------------------

    btc_movement = float(
        btc_data["movement_percent"]
    )

    direction = (
        "UP"
        if btc_movement > 0
        else "DOWN"
    )

    market_price = (
        up_price
        if direction == "UP"
        else down_price
    )

    print()
    print("=" * 70)
    print("STRATEGY INPUT")
    print("=" * 70)

    print(
        f"Direction:       {direction}"
    )

    print(
        f"Market Price:    ${market_price:.4f}"
    )

    print(
        f"Seconds Left:    "
        f"{btc_data['seconds_remaining']}"
    )

    print(
        f"Bankroll:        ${bankroll:.2f}"
    )

    # --------------------------------------------------------
    # Evaluate strategy
    # --------------------------------------------------------

    result = evaluate(
        btc_open=btc_data["btc_open"],
        btc_current=btc_data["btc_current"],
        market_price=market_price,
        seconds_remaining=btc_data["seconds_remaining"],
        bankroll=bankroll,
    )

    # --------------------------------------------------------
    # Strategy result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("STRATEGY RESULT")
    print("=" * 70)

    print(
        f"Signal:          {result.signal}"
    )

    print(
        f"Side:            {result.side}"
    )

    print(
        f"Probability:     "
        f"{float(result.probability) * 100:.2f}%"
    )

    print(
        f"Market Price:    "
        f"${float(result.market_price):.4f}"
    )

    print(
        f"Edge:            "
        f"{float(result.edge) * 100:.2f}%"
    )

    print(
        f"Kelly:           "
        f"{float(result.kelly_fraction) * 100:.2f}%"
    )

    print(
        f"Position Size:   "
        f"${float(result.position_size):.2f}"
    )

    print(
        f"Reason:          {result.reason}"
    )

    print("=" * 70)

    # ========================================================
    # CRITICAL TRADE DECISION
    # ========================================================

    if result.signal is True:

        print()
        print(
            "VALID SIGNAL DETECTED"
        )

        print(
            "Opening PAPER trade..."
        )

        # ----------------------------------------------------
        # THIS IS THE IMPORTANT FIX
        #
        # A valid signal directly calls open_paper_trade().
        # ----------------------------------------------------

        open_paper_trade(
            result=result,
            btc_data=btc_data,
            market_data=market_data,
            bankroll=bankroll,
        )

    else:

        print()
        print(
            "NO PAPER TRADE"
        )

        print(
            f"Reason: {result.reason}"
        )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RUN COMPLETE")
    print("=" * 70)

    print(
        "PAPER ONLY - NO REAL TRADING"
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
