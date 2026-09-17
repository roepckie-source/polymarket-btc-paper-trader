"""
FORSEE BTC 5-MINUTE PREDICTION MARKET DATA

PAPER / READ-ONLY ONLY

This module:
- Reads the current Forsee BTC 5-minute market
- Reads UP/DOWN odds
- Reads BTC open/current price
- Reads round timing
- Reads acceptingOrders
- Does NOT place orders
- Does NOT access positions
- Does NOT access wallet/balance
"""

import os
import sys
from datetime import datetime, timezone

import requests


# ============================================================
# CONFIG
# ============================================================

FORSEE_API_BASE = "https://api.forsee.market/v1"
MARKET_ID = "BTC_FIVE_MINUTES"
REQUEST_TIMEOUT = 15


# ============================================================
# API KEY
# ============================================================

def get_api_key():
    """Read the Forsee API key from the environment."""

    api_key = os.getenv("FORSEE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "FORSEE_API_KEY is not set. "
            "Add it as a GitHub Actions secret."
        )

    return api_key.strip()


# ============================================================
# TIME HELPERS
# ============================================================

def milliseconds_to_seconds(value):
    """
    Convert a millisecond value to seconds.

    Example:
        208291 -> 208.291
    """

    if value is None:
        return None

    try:
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return None


def seconds_value(value):
    """
    Convert an already-second value to float.

    Forsee's timeRemaining is already in seconds.
    """

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# GET MARKET DATA
# ============================================================

def get_market_data():
    """
    Read the current Forsee BTC 5-minute market.

    READ ONLY.

    No POST requests.
    No orders.
    No wallet.
    """

    api_key = get_api_key()

    url = f"{FORSEE_API_BASE}/markets/{MARKET_ID}"

    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "polymarket-btc-paper-trader/1.0",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Forsee API error: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(
            "Forsee API returned success=false: "
            f"{payload.get('error', 'unknown error')}"
        )

    data = payload.get("data")

    if not isinstance(data, dict):
        raise RuntimeError(
            "Unexpected Forsee API data format: "
            f"{type(data).__name__}"
        )

    # --------------------------------------------------------
    # CURRENT ROUND
    # --------------------------------------------------------

    current_round = data.get("currentRound")

    if not isinstance(current_round, dict):
        raise RuntimeError(
            "Forsee response does not contain currentRound."
        )

    # --------------------------------------------------------
    # RAW TIME VALUES
    # --------------------------------------------------------

    raw_time_remaining = current_round.get(
        "timeRemaining"
    )

    raw_time_to_lock = current_round.get(
        "timeToLock"
    )

    raw_time_to_cutoff = current_round.get(
        "timeToOrderCutoff"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # timeRemaining = SECONDS
    # timeToLock = MILLISECONDS
    # timeToOrderCutoff = MILLISECONDS
    # --------------------------------------------------------

    time_remaining_seconds = seconds_value(
        raw_time_remaining
    )

    time_to_lock_seconds = milliseconds_to_seconds(
        raw_time_to_lock
    )

    time_to_cutoff_seconds = milliseconds_to_seconds(
        raw_time_to_cutoff
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    result = {

        # Market
        "market_id": data.get("id"),
        "crypto": data.get("crypto"),
        "timeframe": data.get("timeFrame"),

        # Odds
        "odds_up": data.get("oddsUp"),
        "odds_down": data.get("oddsDown"),

        "percent_up": data.get(
            "percentUp"
        ),

        "percent_down": data.get(
            "percentDown"
        ),

        "odds_source": data.get(
            "oddsSource"
        ),

        # Pools
        "pool_up": data.get(
            "poolUp"
        ),

        "pool_down": data.get(
            "poolDown"
        ),

        "total_pool": data.get(
            "totalPool"
        ),

        # Limits
        "min_bet": data.get(
            "minBet"
        ),

        "max_bet": data.get(
            "maxBet"
        ),

        # Round
        "round_id": current_round.get(
            "id"
        ),

        "round_number": current_round.get(
            "roundNumber"
        ),

        "round_start": current_round.get(
            "startTime"
        ),

        "round_lock": current_round.get(
            "lockTime"
        ),

        "round_end": current_round.get(
            "endTime"
        ),

        # Raw timing
        "time_remaining_raw": raw_time_remaining,

        "time_to_lock_raw": raw_time_to_lock,

        "time_to_order_cutoff_raw": raw_time_to_cutoff,

        # Converted timing
        "time_remaining": time_remaining_seconds,

        "time_to_lock": time_to_lock_seconds,

        "time_to_order_cutoff": (
            time_to_cutoff_seconds
        ),

        # Order status
        "accepting_orders": current_round.get(
            "acceptingOrders"
        ),

        # BTC
        "btc_open": current_round.get(
            "openPrice"
        ),

        "btc_current": current_round.get(
            "currentPrice"
        ),

        # Status
        "status": current_round.get(
            "status"
        ),

        # Timestamp
        "read_timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    return result


# ============================================================
# PRINT MARKET DATA
# ============================================================

def print_market_data(data):

    print()
    print("=" * 60)
    print("FORSEE BTC 5-MINUTE PREDICTION MARKET")
    print("=" * 60)

    print()
    print("PAPER / READ-ONLY")
    print("NO ORDERS")
    print("NO BETS")
    print("NO WALLET")
    print()

    # --------------------------------------------------------
    # MARKET
    # --------------------------------------------------------

    print(
        f"Market ID:             "
        f"{data['market_id']}"
    )

    print(
        f"Crypto:                "
        f"{data['crypto']}"
    )

    print(
        f"Timeframe:             "
        f"{data['timeframe']}"
    )

    # --------------------------------------------------------
    # ROUND
    # --------------------------------------------------------

    print()
    print("ROUND")
    print("-" * 60)

    print(
        f"Round ID:              "
        f"{data['round_id']}"
    )

    print(
        f"Round Number:          "
        f"{data['round_number']}"
    )

    print(
        f"Start:                 "
        f"{data['round_start']}"
    )

    print(
        f"Lock:                  "
        f"{data['round_lock']}"
    )

    print(
        f"End:                   "
        f"{data['round_end']}"
    )

    # --------------------------------------------------------
    # BTC
    # --------------------------------------------------------

    print()
    print("BTC")
    print("-" * 60)

    print(
        f"BTC Open:              "
        f"{data['btc_open']}"
    )

    print(
        f"BTC Current:           "
        f"{data['btc_current']}"
    )

    btc_open = data["btc_open"]
    btc_current = data["btc_current"]

    if (
        btc_open is not None
        and btc_current is not None
        and float(btc_open) != 0
    ):

        movement = (
            (
                float(btc_current)
                - float(btc_open)
            )
            / float(btc_open)
            * 100
        )

        if movement > 0:
            direction = "UP"
        elif movement < 0:
            direction = "DOWN"
        else:
            direction = "FLAT"

        print(
            f"BTC Movement:          "
            f"{movement:+.4f}%"
        )

        print(
            f"BTC Direction:         "
            f"{direction}"
        )

    # --------------------------------------------------------
    # FORSEE ODDS
    # --------------------------------------------------------

    print()
    print("FORSEE ODDS")
    print("-" * 60)

    print(
        f"UP Odds:               "
        f"{data['odds_up']}"
    )

    print(
        f"DOWN Odds:             "
        f"{data['odds_down']}"
    )

    print(
        f"UP Probability:        "
        f"{data['percent_up']}%"
    )

    print(
        f"DOWN Probability:      "
        f"{data['percent_down']}%"
    )

    print(
        f"Odds Source:           "
        f"{data['odds_source']}"
    )

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    print()
    print("TIMING")
    print("-" * 60)

    time_remaining = data[
        "time_remaining"
    ]

    time_to_lock = data[
        "time_to_lock"
    ]

    time_to_cutoff = data[
        "time_to_order_cutoff"
    ]

    if time_remaining is not None:
        print(
            f"Seconds Remaining:     "
            f"{time_remaining:.1f}"
        )
    else:
        print(
            "Seconds Remaining:     None"
        )

    if time_to_lock is not None:
        print(
            f"Seconds To Lock:       "
            f"{time_to_lock:.1f}"
        )
    else:
        print(
            "Seconds To Lock:       None"
        )

    if time_to_cutoff is not None:
        print(
            f"Seconds To Cutoff:     "
            f"{time_to_cutoff:.1f}"
        )
    else:
        print(
            "Seconds To Cutoff:     None"
        )

    # --------------------------------------------------------
    # ORDER STATUS
    # --------------------------------------------------------

    print()
    print("ORDER STATUS")
    print("-" * 60)

    print(
        f"Accepting Orders:      "
        f"{data['accepting_orders']}"
    )

    # --------------------------------------------------------
    # MARKET STATUS
    # --------------------------------------------------------

    print()
    print("MARKET STATUS")
    print("-" * 60)

    print(
        f"Status:                "
        f"{data['status']}"
    )

    # --------------------------------------------------------
    # LIMITS
    # --------------------------------------------------------

    print()
    print("LIMITS")
    print("-" * 60)

    print(
        f"Minimum Bet:           "
        f"${data['min_bet']}"
    )

    print(
        f"Maximum Bet:           "
        f"${data['max_bet']}"
    )

    # --------------------------------------------------------
    # RAW API TIMING
    # --------------------------------------------------------

    print()
    print("RAW API TIMING")
    print("-" * 60)

    print(
        f"timeRemaining:         "
        f"{data['time_remaining_raw']}"
    )

    print(
        f"timeToLock:             "
        f"{data['time_to_lock_raw']}"
    )

    print(
        f"timeToOrderCutoff:      "
        f"{data['time_to_order_cutoff_raw']}"
    )

    # --------------------------------------------------------
    # READ TIMESTAMP
    # --------------------------------------------------------

    print()

    print(
        f"Read UTC:              "
        f"{data['read_timestamp']}"
    )

    print()

    print("=" * 60)
    print("FORSEE READ TEST COMPLETE")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        data = get_market_data()

        print_market_data(data)

    except Exception as exc:

        print()
        print("=" * 60)
        print("FORSEE TEST FAILED")
        print("=" * 60)
        print()

        print(str(exc))

        print()

        sys.exit(1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
