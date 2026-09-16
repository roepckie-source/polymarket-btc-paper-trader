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
from market_data import get_market_data as get_btc_market_data
from polymarket_data import get_market_data as get_polymarket_market_data


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

    if not os.path.exists(STATE_FILE):
        return PAPER_BANKROLL

    try:

        with open(
            STATE_FILE,
            "r",
            newline="",
            encoding="utf-8",
        ) as f:

            reader = csv.DictReader(f)

            for row in reader:

                value = row.get("bankroll")

                if value is not None:
                    return float(value)

    except Exception as exc:

        print(
            f"WARNING: Could not load bankroll: {exc}"
        )

    return PAPER_BANKROLL


def save_bankroll(bankroll):

    with open(
        STATE_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

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

    if not os.path.exists(TRADES_FILE):
        return None

    try:

        with open(
            TRADES_FILE,
            "r",
            newline="",
            encoding="utf-8",
        ) as f:

            reader = csv.DictReader(f)

            for row in reader:

                if row.get("status") == "OPEN":
                    return row

    except Exception as exc:

        print(
            f"WARNING: Could not load trades: {exc}"
        )

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

    "market_slug",
    "condition_id",
]


def append_trade(trade):

    file_exists = os.path.exists(TRADES_FILE)

    with open(
        TRADES_FILE,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=TRADE_FIELDS,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(trade)


def read_all_trades():

    if not os.path.exists(TRADES_FILE):
        return []

    trades = []

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

    except Exception as exc:

        print(
            f"WARNING: Could not read trades: {exc}"
        )

    return trades


def rewrite_trades(trades):

    with open(
        TRADES_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=TRADE_FIELDS,
        )

        writer.writeheader()

        for trade in trades:
            writer.writerow(trade)


def next_trade_id():

    trades = read_all_trades()

    highest = 0

    for trade in trades:

        try:

            trade_id = int(
                trade.get(
                    "trade_id",
                    0,
                )
            )

            highest = max(
                highest,
                trade_id,
            )

        except (
            ValueError,
            TypeError,
        ):

            pass

    return highest + 1


# ============================================================
# RESOLVE TRADE
# ============================================================

def resolve_open_trade(
    open_trade,
    btc_data,
    bankroll,
):

    if open_trade is None:
        return bankroll

    previous_window_start = int(
        float(
            open_trade["window_start"]
        )
    )

    current_window_start = int(
        btc_data["window_start"]
    )

    # --------------------------------------------------------
    # Same window = trade still open
    # --------------------------------------------------------

    if current_window_start <= previous_window_start:

        return bankroll

    # --------------------------------------------------------
    # Previous window BTC close
    #
    # The new 5m candle open represents the transition
    # into the new window and is therefore used as the
    # previous window's closing reference.
    # --------------------------------------------------------

    btc_close = float(
        btc_data["btc_open"]
    )

    btc_open = float(
        open_trade["btc_open"]
    )

    movement_percent = (
        (
            btc_close
            - btc_open
        )
        / btc_open
        * 100.0
    )

    if movement_percent > 0:

        winning_side = "UP"

    else:

        winning_side = "DOWN"

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
    # WIN
    # --------------------------------------------------------

    if trade_side == winning_side:

        payout = contracts

        pnl = (
            payout
            - position_size
        )

        result = "WIN"

    # --------------------------------------------------------
    # LOSS
    # --------------------------------------------------------

    else:

        payout = 0.0

        pnl = -position_size

        result = "LOSS"

    bankroll_before = bankroll

    bankroll_after = (
        bankroll
        + pnl
    )

    # --------------------------------------------------------
    # Update trade
    # --------------------------------------------------------

    trades = read_all_trades()

    updated = False

    for trade in trades:

        if (
            trade.get("trade_id")
            == open_trade.get("trade_id")
            and trade.get("status")
            == "OPEN"
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

            updated = True

    if updated:

        rewrite_trades(trades)

    save_bankroll(
        bankroll_after
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAPER TRADE RESOLVED")
    print("=" * 70)

    print(
        f"Trade ID:       "
        f"{open_trade['trade_id']}"
    )

    print(
        f"Side:           "
        f"{trade_side}"
    )

    print(
        f"BTC Open:       "
        f"${btc_open:,.2f}"
    )

    print(
        f"BTC Close:      "
        f"${btc_close:,.2f}"
    )

    print(
        f"BTC Movement:   "
        f"{movement_percent:+.4f}%"
    )

    print(
        f"Winning Side:   "
        f"{winning_side}"
    )

    print(
        f"Result:         "
        f"{result}"
    )

    print(
        f"Position:       "
        f"${position_size:.2f}"
    )

    print(
        f"Contracts:      "
        f"{contracts:.4f}"
    )

    print(
        f"Payout:         "
        f"${payout:.2f}"
    )

    print(
        f"P&L:            "
        f"${pnl:+.2f}"
    )

    print(
        f"Bankroll:       "
        f"${bankroll_before:.2f}"
        f" -> "
        f"${bankroll_after:.2f}"
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
    polymarket_data,
    bankroll,
):

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
    # Safety checks
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

    if side not in (
        "UP",
        "DOWN",
    ):

        print(
            "ERROR: Invalid side."
        )

        return bankroll

    if position_size > bankroll:

        print(
            "ERROR: Position exceeds bankroll."
        )

        return bankroll

    # --------------------------------------------------------
    # Contracts
    # --------------------------------------------------------

    contracts = (
        position_size
        / market_price
    )

    trade_id = next_trade_id()

    # --------------------------------------------------------
    # Market information
    # --------------------------------------------------------

    market_slug = polymarket_data.get(
        "market_slug",
        "",
    )

    condition_id = polymarket_data.get(
        "condition_id",
        "",
    )

    # --------------------------------------------------------
    # Create trade
    # --------------------------------------------------------

    trade = {

        "trade_id": trade_id,

        "status": "OPEN",

        "opened_at": utc_now(),

        "resolved_at": "",

        "window_start": window_start,

        "window_end": window_end,

        "side": side,

        "btc_open": (
            f"{btc_open:.2f}"
        ),

        "btc_entry": (
            f"{btc_current:.2f}"
        ),

        "btc_close": "",

        "market_price": (
            f"{market_price:.8f}"
        ),

        "contracts": (
            f"{contracts:.8f}"
        ),

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

        "market_slug": market_slug,

        "condition_id": condition_id,
    }

    append_trade(
        trade
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAPER TRADE OPENED")
    print("=" * 70)

    print(
        f"Trade ID:       "
        f"{trade_id}"
    )

    print(
        f"Side:           "
        f"{side}"
    )

    print(
        f"BTC Open:       "
        f"${btc_open:,.2f}"
    )

    print(
        f"BTC Current:    "
        f"${btc_current:,.2f}"
    )

    print(
        f"Market Price:   "
        f"${market_price:.4f}"
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
        f"Position Size:  "
        f"${position_size:.2f}"
    )

    print(
        f"Contracts:      "
        f"{contracts:.4f}"
    )

    print(
        f"Bankroll:       "
        f"${bankroll:.2f}"
    )

    print(
        f"Market:         "
        f"{market_slug}"
    )

    print()
    print(
        "STATUS: OPEN"
    )

    print(
        "PAPER ONLY - NO REAL ORDER"
    )

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
    # BANKROLL
    # --------------------------------------------------------

    bankroll = load_bankroll()

    print(
        f"Current PAPER BANKROLL: "
        f"${bankroll:.2f}"
    )

    # --------------------------------------------------------
    # BTC DATA
    # --------------------------------------------------------

    print()
    print(
        "Loading BTC market data..."
    )

    try:

        btc_data = (
            get_btc_market_data()
        )

    except Exception as exc:

        print(
            f"ERROR: BTC market data failed: {exc}"
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
    # DATA SOURCE SAFETY
    # --------------------------------------------------------

    if (
        btc_data["source"]
        != EXPECTED_BTC_SOURCE
    ):

        print()
        print(
            "ERROR: Unexpected BTC data source."
        )

        print(
            f"Expected: "
            f"{EXPECTED_BTC_SOURCE}"
        )

        print(
            f"Actual: "
            f"{btc_data['source']}"
        )

        return

    # --------------------------------------------------------
    # POLYMARKET DATA
    # --------------------------------------------------------

    print()
    print(
        "Loading Polymarket market data..."
    )

    try:

        polymarket_data = (
            get_polymarket_market_data()
        )

    except Exception as exc:

        print(
            f"ERROR: Polymarket market data failed: {exc}"
        )

        return

    print(
        f"Question:        "
        f"{polymarket_data.get('question')}"
    )

    print(
        f"Market:          "
        f"{polymarket_data.get('market_slug')}"
    )

    print(
        f"Seconds Left:    "
        f"{polymarket_data.get('seconds_remaining')}"
    )

    outcome_prices = (
        polymarket_data.get(
            "outcome_prices",
            {},
        )
    )

    try:

        up_price = float(
            outcome_prices["UP"]
        )

        down_price = float(
            outcome_prices["DOWN"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        print(
            "ERROR: UP/DOWN prices unavailable."
        )

        return

    print(
        f"UP Price:        "
        f"{up_price:.3f}"
    )

    print(
        f"DOWN Price:      "
        f"{down_price:.3f}"
    )

    # --------------------------------------------------------
    # RESOLVE EXISTING TRADE FIRST
    # --------------------------------------------------------

    open_trade = (
        load_open_trade()
    )

    if open_trade is not None:

        print()
        print(
            "OPEN PAPER TRADE DETECTED"
        )

        print(
            f"Trade ID: "
            f"{open_trade['trade_id']}"
        )

        print(
            f"Side:     "
            f"{open_trade['side']}"
        )

        print(
            f"Window:   "
            f"{open_trade['window_start']}"
        )

        bankroll = (
            resolve_open_trade(
                open_trade,
                btc_data,
                bankroll,
            )
        )

    # --------------------------------------------------------
    # CHECK AGAIN
    # --------------------------------------------------------

    open_trade = (
        load_open_trade()
    )

    if open_trade is not None:

        print()
        print(
            "OPEN TRADE STILL ACTIVE"
        )

        print(
            f"Trade ID: "
            f"{open_trade['trade_id']}"
        )

        print(
            "No new trade will be opened."
        )

        print()
        print("=" * 70)
        print("RUN COMPLETE")
        print("=" * 70)
        print(
            "PAPER ONLY - NO REAL TRADING"
        )

        return

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    movement = float(
        btc_data["movement_percent"]
    )

    direction = (
        "UP"
        if movement > 0
        else "DOWN"
    )

    market_price = (
        up_price
        if direction == "UP"
        else down_price
    )

    # --------------------------------------------------------
    # STRATEGY INPUT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("STRATEGY INPUT")
    print("=" * 70)

    print(
        f"Direction:       "
        f"{direction}"
    )

    print(
        f"Market Price:    "
        f"${market_price:.4f}"
    )

    print(
        f"Seconds Left:    "
        f"{btc_data['seconds_remaining']}"
    )

    print(
        f"Bankroll:        "
        f"${bankroll:.2f}"
    )

    # --------------------------------------------------------
    # STRATEGY
    # --------------------------------------------------------

    result = evaluate(
        btc_open=btc_data["btc_open"],
        btc_current=btc_data["btc_current"],
        market_price=market_price,
        seconds_remaining=btc_data[
            "seconds_remaining"
        ],
        bankroll=bankroll,
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("STRATEGY RESULT")
    print("=" * 70)

    print(
        f"Signal:          "
        f"{result.signal}"
    )

    print(
        f"Side:            "
        f"{result.side}"
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
        f"Kelly:            "
        f"{float(result.kelly_fraction) * 100:.2f}%"
    )

    print(
        f"Position Size:   "
        f"${float(result.position_size):.2f}"
    )

    print(
        f"Reason:          "
        f"{result.reason}"
    )

    print("=" * 70)

    # ========================================================
    # VALID SIGNAL
    # ========================================================

    if result.signal:

        print()
        print(
            "VALID SIGNAL DETECTED"
        )

        print(
            "Opening PAPER trade..."
        )

        open_paper_trade(
            result=result,
            btc_data=btc_data,
            polymarket_data=polymarket_data,
            bankroll=bankroll,
        )

    else:

        print()
        print(
            "NO PAPER TRADE"
        )

        print(
            f"Reason: "
            f"{result.reason}"
        )

    # --------------------------------------------------------
    # END
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