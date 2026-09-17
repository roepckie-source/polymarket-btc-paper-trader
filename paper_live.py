import csv
import json
import os
from datetime import datetime, timezone

import requests

from market_data import get_market_data as get_btc_market_data
from polymarket_data import get_market_data as get_polymarket_market_data


# ============================================================
# CONFIG
# ============================================================

PAPER_BANKROLL = 100.00

# HARD SAFETY: this file is paper-only.
LIVE_TRADING = False

TRADES_FILE = "paper_trades.csv"
STATE_FILE = "paper_state.csv"

CLOB_BASE_URL = "https://clob.polymarket.com"
GAMMA_BASE_URL = "https://gamma-api.polymarket.com"

EXPECTED_BTC_SOURCE = "Kraken 5m candle + Coinbase ticker"

REQUEST_TIMEOUT = 10


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
        with open(STATE_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader, None)

        if row and row.get("bankroll"):
            return float(row["bankroll"])

    except Exception as e:
        print(f"WARNING: Could not load bankroll: {e}")

    return PAPER_BANKROLL


def save_bankroll(bankroll):
    with open(STATE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bankroll"])
        writer.writerow([f"{bankroll:.8f}"])


# ============================================================
# OPEN TRADE
# ============================================================

def load_open_trade():
    if not os.path.exists(TRADES_FILE):
        return None

    try:
        with open(TRADES_FILE, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        for row in reversed(rows):
            if row.get("status") == "OPEN":
                return row

    except Exception as e:
        print(f"WARNING: Could not load open trade: {e}")

    return None


# ============================================================
# TRADE ID
# ============================================================

def next_trade_id():
    if not os.path.exists(TRADES_FILE):
        return 1

    try:
        with open(TRADES_FILE, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            return 1

        ids = []

        for row in rows:
            try:
                ids.append(int(row["trade_id"]))
            except Exception:
                pass

        return max(ids) + 1 if ids else 1

    except Exception:
        return 1


# ============================================================
# CSV
# ============================================================

TRADE_FIELDS = [
    "trade_id",
    "opened_at",
    "resolved_at",
    "status",
    "side",
    "btc_open",
    "btc_entry",
    "btc_close",
    "btc_movement_percent",
    "market_price",
    "probability",
    "edge",
    "kelly",
    "position_size",
    "contracts",
    "fee_rate",
    "fee_rate_bps",
    "fee_usdc",
    "payout",
    "gross_pnl",
    "net_pnl",
    "result",
    "market_slug",
    "condition_id",

    # Kept for audit/debugging of the BTC 5-minute window.
    # It is NOT used for trade settlement.
    "window_start",
]


def append_trade(data):
    exists = os.path.exists(TRADES_FILE)

    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=TRADE_FIELDS,
            extrasaction="ignore",
        )

        if not exists:
            writer.writeheader()

        writer.writerow(data)


def rewrite_trades(rows):
    with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=TRADE_FIELDS,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# POLYMARKET FEE
# ============================================================

def get_fee_info(condition_id, token_id):
    """
    Get fee information for the actual Polymarket market.

    Primary:
        GET /clob-markets/{condition_id}

    Fallback:
        GET /fee-rate?token_id=...

    Returns:
        {
            "rate": float,
            "bps": int,
            "source": str
        }
    """

    # --------------------------------------------------------
    # PRIMARY: CLOB MARKET INFO
    # --------------------------------------------------------

    if condition_id:
        try:
            url = f"{CLOB_BASE_URL}/clob-markets/{condition_id}"

            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            data = response.json()

            fd = data.get("fd")

            if isinstance(fd, dict):
                rate = float(fd.get("r", 0.0))

                if rate >= 0:
                    return {
                        "rate": rate,
                        "bps": round(rate * 10000),
                        "source": "CLOB market fd",
                    }

        except Exception as e:
            print(
                f"WARNING: Could not read CLOB market fee info: {e}"
            )

    # --------------------------------------------------------
    # FALLBACK: FEE RATE ENDPOINT
    # --------------------------------------------------------

    if token_id:
        try:
            url = f"{CLOB_BASE_URL}/fee-rate"

            response = requests.get(
                url,
                params={"token_id": token_id},
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            data = response.json()

            base_fee = data.get("base_fee", 0)

            bps = int(base_fee)

            return {
                "rate": bps / 10000.0,
                "bps": bps,
                "source": "CLOB fee-rate",
            }

        except Exception as e:
            print(
                f"WARNING: Could not read fee-rate: {e}"
            )

    # --------------------------------------------------------
    # SAFE FALLBACK
    # --------------------------------------------------------

    return {
        "rate": 0.0,
        "bps": 0,
        "source": "fallback 0",
    }


# ============================================================
# FEE CALCULATION
# ============================================================

def calculate_fee(contracts, price, fee_rate):
    """
    Polymarket formula:

        fee = C * feeRate * p * (1-p)

    C = number of shares
    p = share price
    """

    if contracts <= 0:
        return 0.0

    if price <= 0 or price >= 1:
        return 0.0

    fee = contracts * fee_rate * price * (1.0 - price)

    return round(fee, 5)


# ============================================================
# POLYMARKET MARKET LOOKUP
# ============================================================

def get_polymarket_market_by_slug(slug):
    if not slug:
        return None

    try:
        url = f"{GAMMA_BASE_URL}/events/slug/{slug}"

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:
        print(
            f"WARNING: Could not load Polymarket event "
            f"{slug}: {e}"
        )

        return None


# ============================================================
# OFFICIAL POLYMARKET RESOLUTION
# ============================================================

def get_resolved_side(market_slug):
    """
    Determine the official Polymarket outcome.

    IMPORTANT:
    A market is only considered resolved when Polymarket marks
    the market/event as closed AND one outcome is settled at
    >= 0.999.

    We deliberately do NOT use BTC candle data as a substitute
    for Polymarket settlement.

    Returns:
        UP
        DOWN
        None
    """

    event = get_polymarket_market_by_slug(market_slug)

    if not event:
        return None

    event_closed = bool(event.get("closed", False))

    markets = event.get("markets", [])

    if not markets:
        return None

    for market in markets:

        market_slug_value = market.get("slug", "")

        # Prefer exact market if the event contains multiple markets.
        if market_slug_value and market_slug_value != market_slug:
            continue

        market_closed = bool(market.get("closed", False))

        if not (event_closed or market_closed):
            continue

        outcomes = market.get("outcomes")
        prices = market.get("outcomePrices")

        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except Exception:
                outcomes = None

        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                prices = None

        if not outcomes or not prices:
            continue

        if len(outcomes) < 2 or len(prices) < 2:
            continue

        try:
            normalized = [
                str(x).strip().upper()
                for x in outcomes
            ]

            numeric_prices = [
                float(x)
                for x in prices
            ]

            for i, outcome in enumerate(normalized):

                if i >= len(numeric_prices):
                    continue

                if outcome in ("UP", "YES"):
                    if numeric_prices[i] >= 0.999:
                        return "UP"

                if outcome in ("DOWN", "NO"):
                    if numeric_prices[i] >= 0.999:
                        return "DOWN"

        except Exception:
            continue

    return None


# ============================================================
# RESOLVE OPEN TRADE
# ============================================================

def resolve_open_trade(open_trade, bankroll):

    trade_id = open_trade["trade_id"]
    side = open_trade["side"]
    market_slug = open_trade["market_slug"]

    print()
    print("OPEN PAPER TRADE DETECTED")
    print(f"Trade ID: {trade_id}")
    print(f"Side:     {side}")
    print(f"Market:   {market_slug}")

    # --------------------------------------------------------
    # OFFICIAL POLYMARKET PUBLIC RESOLUTION ONLY
    # --------------------------------------------------------

    winning_side = get_resolved_side(market_slug)

    resolution_source = "Polymarket official public resolution"

    # --------------------------------------------------------
    # STILL OPEN
    # --------------------------------------------------------

    if winning_side is None:

        print()
        print(
            "Polymarket official resolution not yet available."
        )

        print(
            "TRADE REMAINS OPEN"
        )

        print(
            "No BTC fallback is used."
        )

        return bankroll

    # --------------------------------------------------------
    # NUMBERS
    # --------------------------------------------------------

    position = float(
        open_trade["position_size"]
    )

    contracts = float(
        open_trade["contracts"]
    )

    market_price = float(
        open_trade["market_price"]
    )

    fee_rate = float(
        open_trade.get("fee_rate") or 0
    )

    fee_usdc = float(
        open_trade.get("fee_usdc") or 0
    )

    # Winning shares pay $1 each.
    payout = (
        contracts
        if winning_side == side
        else 0.0
    )

    gross_pnl = payout - position

    net_pnl = gross_pnl - fee_usdc

    new_bankroll = bankroll + net_pnl

    result = (
        "WIN"
        if winning_side == side
        else "LOSS"
    )

    # --------------------------------------------------------
    # BTC INFORMATION
    # Diagnostic only.
    # NOT used to determine WIN/LOSS.
    # --------------------------------------------------------

    btc_close = ""

    try:

        btc_data = get_btc_market_data()

        btc_close = float(
            btc_data["btc_open"]
        )

    except Exception:
        pass

    btc_open = float(
        open_trade["btc_open"]
    )

    btc_movement = ""

    if btc_close:

        btc_movement = (
            (btc_close - btc_open)
            / btc_open
            * 100
        )

    # --------------------------------------------------------
    # UPDATE CSV
    # --------------------------------------------------------

    try:

        with open(
            TRADES_FILE,
            "r",
            newline="",
            encoding="utf-8",
        ) as f:

            rows = list(
                csv.DictReader(f)
            )

        for row in rows:

            if row["trade_id"] == trade_id:

                row["status"] = "CLOSED"

                row["resolved_at"] = utc_now()

                row["btc_close"] = (
                    f"{btc_close:.8f}"
                    if btc_close
                    else ""
                )

                row["btc_movement_percent"] = (
                    f"{btc_movement:.8f}"
                    if btc_movement != ""
                    else ""
                )

                row["payout"] = (
                    f"{payout:.8f}"
                )

                row["gross_pnl"] = (
                    f"{gross_pnl:.8f}"
                )

                row["net_pnl"] = (
                    f"{net_pnl:.8f}"
                )

                row["result"] = result

                break

        rewrite_trades(rows)

    except Exception as e:

        print(
            f"WARNING: Could not update trade CSV: {e}"
        )

    save_bankroll(new_bankroll)

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAPER TRADE RESOLVED - OFFICIAL POLYMARKET RESULT")
    print("=" * 70)

    print(f"Trade ID:          {trade_id}")
    print(f"Side:              {side}")

    if btc_close:

        print(
            f"BTC Open:          ${btc_open:,.2f}"
        )

        print(
            f"BTC Close:         ${btc_close:,.2f}"
        )

    print(
        f"Winning Side:      {winning_side}"
    )

    print(
        f"Resolution:        {resolution_source}"
    )

    print(
        f"Result:             {result}"
    )

    print(
        f"Position:          ${position:.2f}"
    )

    print(
        f"Contracts:         {contracts:.4f}"
    )

    print(
        f"Gross P&L:         ${gross_pnl:+.2f}"
    )

    print(
        f"Trading Fee:       ${fee_usdc:.5f}"
    )

    print(
        f"Net P&L:           ${net_pnl:+.2f}"
    )

    print(
        f"Bankroll:          "
        f"${bankroll:.2f} -> ${new_bankroll:.2f}"
    )

    print("=" * 70)

    return new_bankroll


# ============================================================
# OPEN PAPER TRADE
# ============================================================

def open_paper_trade(
    result,
    btc_data,
    polymarket_data,
    bankroll,
):

    trade_id = next_trade_id()

    side = result.side

    position_size = float(
        result.position_size
    )

    market_price = float(
        result.market_price
    )

    contracts = (
        position_size / market_price
    )

    condition_id = polymarket_data.get(
        "condition_id",
        "",
    )

    token_ids = polymarket_data.get(
        "token_ids",
        [],
    )

    token_id = ""

    if isinstance(token_ids, list) and token_ids:

        if side.upper() == "UP":

            token_id = str(
                token_ids[0]
            )

        elif len(token_ids) > 1:

            token_id = str(
                token_ids[1]
            )

    # --------------------------------------------------------
    # FEE
    # --------------------------------------------------------

    fee_info = get_fee_info(
        condition_id,
        token_id,
    )

    fee_rate = float(
        fee_info["rate"]
    )

    fee_rate_bps = int(
        fee_info["bps"]
    )

    fee_usdc = calculate_fee(
        contracts,
        market_price,
        fee_rate,
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAPER TRADE OPENED")
    print("=" * 70)

    print(
        f"Trade ID:       {trade_id}"
    )

    print(
        f"Side:           {side}"
    )

    print(
        f"BTC Open:       "
        f"${float(btc_data['btc_open']):,.2f}"
    )

    print(
        f"BTC Current:    "
        f"${float(btc_data['btc_current']):,.2f}"
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
        f"Fee Rate:       "
        f"{fee_rate * 100:.4f}%"
    )

    print(
        f"Fee Rate BPS:   {fee_rate_bps}"
    )

    print(
        f"Estimated Fee:  ${fee_usdc:.5f}"
    )

    print(
        f"Market:         "
        f"{polymarket_data.get('market_slug', '')}"
    )

    print(
        f"Fee Source:     {fee_info['source']}"
    )

    print()

    print("STATUS: OPEN")
    print("PAPER ONLY - NO REAL ORDER")

    print("=" * 70)

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    row = {
        "trade_id": trade_id,

        "opened_at": utc_now(),

        "resolved_at": "",

        "status": "OPEN",

        "side": side,

        "btc_open": (
            f"{float(btc_data['btc_open']):.8f}"
        ),

        "btc_entry": (
            f"{float(btc_data['btc_current']):.8f}"
        ),

        "btc_close": "",

        "btc_movement_percent": (
            f"{float(btc_data['movement_percent']):.8f}"
        ),

        "market_price": (
            f"{market_price:.8f}"
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

        "contracts": (
            f"{contracts:.8f}"
        ),

        "fee_rate": (
            f"{fee_rate:.8f}"
        ),

        "fee_rate_bps": str(
            fee_rate_bps
        ),

        "fee_usdc": (
            f"{fee_usdc:.8f}"
        ),

        "payout": "",

        "gross_pnl": "",

        "net_pnl": "",

        "result": "",

        "market_slug": polymarket_data.get(
            "market_slug",
            "",
        ),

        "condition_id": condition_id,

        "window_start": btc_data.get(
            "window_start",
            "",
        ),
    }

    append_trade(row)


# ============================================================
# MAIN
# ============================================================

def main():

    if LIVE_TRADING:
        raise RuntimeError(
            "LIVE_TRADING must remain False in paper_live.py"
        )

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
    print("OFFICIAL POLYMARKET RESOLUTION ONLY")

    bankroll = load_bankroll()

    print()
    print(
        f"Current PAPER BANKROLL: ${bankroll:.2f}"
    )

    # --------------------------------------------------------
    # CHECK OPEN TRADE FIRST
    # --------------------------------------------------------

    open_trade = load_open_trade()

    if open_trade:

        print()

        print(
            f"Existing open trade detected: "
            f"#{open_trade['trade_id']}"
        )

        bankroll = resolve_open_trade(
            open_trade,
            bankroll,
        )

        # Reload in case trade is still open.
        open_trade = load_open_trade()

        if open_trade:

            print()
            print(
                "Existing trade remains OPEN."
            )

            print(
                "No new trade will be opened."
            )

            print()
            print("=" * 70)
            print("RUN COMPLETE")
            print("=" * 70)
            print("PAPER ONLY - NO REAL TRADING")

            return

    # --------------------------------------------------------
    # BTC
    # --------------------------------------------------------

    print()
    print("Loading BTC market data...")

    btc_data = get_btc_market_data()

    print(
        f"BTC Open:        "
        f"${float(btc_data['btc_open']):,.2f}"
    )

    print(
        f"BTC Current:     "
        f"${float(btc_data['btc_current']):,.2f}"
    )

    print(
        f"BTC Movement:    "
        f"{float(btc_data['movement_percent']):+.4f}%"
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
    # POLYMARKET
    # --------------------------------------------------------

    print()
    print("Loading Polymarket market data...")

    polymarket_data = get_polymarket_market_data()

    print(
        f"Question:        "
        f"{polymarket_data['question']}"
    )

    print(
        f"Market:          "
        f"{polymarket_data['market_slug']}"
    )

    print(
        f"Seconds Left:    "
        f"{polymarket_data['seconds_remaining']}"
    )

    prices = polymarket_data.get(
        "outcome_prices",
        {},
    )

    up_price = float(
        prices.get("UP", 0)
    )

    down_price = float(
        prices.get("DOWN", 0)
    )

    print(
        f"UP Price:        {up_price:.3f}"
    )

    print(
        f"DOWN Price:      {down_price:.3f}"
    )

    # --------------------------------------------------------
    # STRATEGY INPUT
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
    # STRATEGY
    # --------------------------------------------------------

    from strategy import evaluate

    result = evaluate(
        btc_open=float(
            btc_data["btc_open"]
        ),

        btc_current=float(
            btc_data["btc_current"]
        ),

        market_price=market_price,

        seconds_remaining=int(
            btc_data["seconds_remaining"]
        ),

        bankroll=bankroll,
    )

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
        f"Edge:             "
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

    # --------------------------------------------------------
    # OPEN
    # --------------------------------------------------------

    if result.signal:

        print()
        print(
            "VALID SIGNAL DETECTED"
        )

        print(
            "Opening PAPER trade..."
        )

        open_paper_trade(
            result,
            btc_data,
            polymarket_data,
            bankroll,
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
    # DONE
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RUN COMPLETE")
    print("=" * 70)
    print("PAPER ONLY - NO REAL TRADING")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
