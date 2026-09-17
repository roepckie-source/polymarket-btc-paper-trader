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


FORSEE_API_BASE = "https://api.forsee.market/v1"
MARKET_ID = "BTC_FIVE_MINUTES"

REQUEST_TIMEOUT = 15


def get_api_key():
    """
    Read the Forsee API key from the environment.

    Expected environment variable:
        FORSEE_API_KEY
    """

    api_key = os.getenv("FORSEE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "FORSEE_API_KEY is not set. "
            "Add it as a GitHub Actions secret or environment variable."
        )

    return api_key.strip()


def get_market_data():
    """
    Read the current Forsee BTC 5-minute market.

    READ ONLY.
    No order endpoint is used.
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
            f"Forsee API returned success=false: "
            f"{payload.get('error', 'unknown error')}"
        )

    data = payload.get("data")

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Unexpected Forsee API data format: {type(data).__name__}"
        )

    current_round = data.get("currentRound")

    if not isinstance(current_round, dict):
        raise RuntimeError(
            "Forsee response does not contain currentRound."
        )

    result = {
        # Market
        "market_id": data.get("id"),
        "crypto": data.get("crypto"),
        "timeframe": data.get("timeFrame"),

        # Live odds
        "odds_up": data.get("oddsUp"),
        "odds_down": data.get("oddsDown"),
        "percent_up": data.get("percentUp"),
        "percent_down": data.get("percentDown"),
        "odds_source": data.get("oddsSource"),

        # Pools
        "pool_up": data.get("poolUp"),
        "pool_down": data.get("poolDown"),
        "total_pool": data.get("totalPool"),

        # Limits
        "min_bet": data.get("minBet"),
        "max_bet": data.get("maxBet"),

        # Current round
        "round_id": current_round.get("id"),
        "round_number": current_round.get("roundNumber"),
        "round_start": current_round.get("startTime"),
        "round_lock": current_round.get("lockTime"),
        "round_end": current_round.get("endTime"),

        # Timing
        "time_remaining": current_round.get("timeRemaining"),
        "time_to_lock": current_round.get("timeToLock"),
        "order_cutoff_time": current_round.get("orderCutoffTime"),
        "time_to_order_cutoff": current_round.get(
            "timeToOrderCutoff"
        ),

        # Order status
        "accepting_orders": current_round.get("acceptingOrders"),

        # BTC prices
        "btc_open": current_round.get("openPrice"),
        "btc_current": current_round.get("currentPrice"),

        # Round status
        "status": current_round.get("status"),

        # Timestamp of our read
        "read_timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    return result


def print_market_data(data):
    """
    Print a clean human-readable report.
    """

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

    print(f"Market ID:             {data['market_id']}")
    print(f"Crypto:                {data['crypto']}")
    print(f"Timeframe:             {data['timeframe']}")

    print()
    print("ROUND")
    print("-" * 60)
    print(f"Round ID:              {data['round_id']}")
    print(f"Round Number:          {data['round_number']}")
    print(f"Start:                 {data['round_start']}")
    print(f"Lock:                  {data['round_lock']}")
    print(f"End:                   {data['round_end']}")

    print()
    print("BTC")
    print("-" * 60)
    print(f"BTC Open:              {data['btc_open']}")
    print(f"BTC Current:           {data['btc_current']}")

    if (
        data["btc_open"] is not None
        and data["btc_current"] is not None
        and data["btc_open"] != 0
    ):
        movement = (
            (data["btc_current"] - data["btc_open"])
            / data["btc_open"]
            * 100
        )

        direction = "UP" if movement > 0 else "DOWN"

        print(f"BTC Movement:          {movement:+.4f}%")
        print(f"BTC Direction:         {direction}")

    print()
    print("FORSEE ODDS")
    print("-" * 60)
    print(f"UP Odds:               {data['odds_up']}")
    print(f"DOWN Odds:             {data['odds_down']}")
    print(f"UP Probability:        {data['percent_up']}%")
    print(f"DOWN Probability:      {data['percent_down']}%")
    print(f"Odds Source:           {data['odds_source']}")

    print()
    print("TIMING")
    print("-" * 60)
    print(f"Seconds Remaining:     {data['time_remaining']}")
    print(f"Seconds To Lock:       {data['time_to_lock']}")
    print(
        f"Seconds To Cutoff:     "
        f"{data['time_to_order_cutoff']}"
    )

    print()
    print("ORDER STATUS")
    print("-" * 60)
    print(f"Accepting Orders:      {data['accepting_orders']}")

    print()
    print("MARKET STATUS")
    print("-" * 60)
    print(f"Status:                {data['status']}")

    print()
    print("LIMITS")
    print("-" * 60)
    print(f"Minimum Bet:           ${data['min_bet']}")
    print(f"Maximum Bet:           ${data['max_bet']}")

    print()
    print(f"Read UTC:              {data['read_timestamp']}")

    print()
    print("=" * 60)
    print("FORSEE READ TEST COMPLETE")
    print("=" * 60)


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


if __name__ == "__main__":
    main()
