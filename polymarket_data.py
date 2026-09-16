"""
Polymarket BTC 5-Minute Market Data

PAPER / READ-ONLY ONLY

- No API keys
- No wallet
- No private keys
- No orders
- No trading
"""

import json
import re
import time
from datetime import datetime, timezone

import requests


GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"

TIMEOUT = 10

BTC_5M_PATTERN = re.compile(
    r"^btc-updown-5m-(\d+)$",
    re.IGNORECASE,
)


def utc_now():
    return datetime.now(timezone.utc)


def get_active_events():
    params = {
        "active": "true",
        "closed": "false",
        "limit": 100,
    }

    response = requests.get(
        GAMMA_EVENTS_URL,
        params=params,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def get_slug_timestamp(slug):
    """
    Extract the Unix timestamp from:

    btc-updown-5m-XXXXXXXXXX
    """

    if not slug:
        return None

    match = BTC_5M_PATTERN.match(str(slug))

    if not match:
        return None

    return int(match.group(1))


def find_current_btc_market(events):
    """
    Find the BTC 5-minute market whose Unix timestamp
    contains the current UTC time.

    Each market lasts exactly 300 seconds.
    """

    now_timestamp = int(time.time())

    candidates = []

    for event in events:

        slug = event.get("slug", "")

        start_timestamp = get_slug_timestamp(slug)

        if start_timestamp is None:
            continue

        end_timestamp = start_timestamp + 300

        # Current time lies inside this 5-minute market
        if start_timestamp <= now_timestamp < end_timestamp:

            candidates.append(
                (
                    start_timestamp,
                    event,
                )
            )

    if not candidates:
        return None

    # In case there are multiple candidates,
    # use the newest start timestamp.
    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1]


def parse_array(value):
    """
    Polymarket sometimes returns arrays as JSON strings.
    """

    if isinstance(value, str):

        try:
            return json.loads(value)
        except json.JSONDecodeError:

            return []

    return value or []


def extract_market(event):

    markets = event.get("markets", [])

    if not markets:
        raise RuntimeError(
            "Event found but contains no market."
        )

    for market in markets:

        outcomes = parse_array(
            market.get("outcomes", "[]")
        )

        prices = parse_array(
            market.get("outcomePrices", "[]")
        )

        token_ids = parse_array(
            market.get("clobTokenIds", "[]")
        )

        if len(outcomes) >= 2:

            return {
                "event_title": event.get("title"),
                "event_slug": event.get("slug"),
                "question": market.get("question"),
                "condition_id": market.get(
                    "conditionId"
                ),
                "market_slug": market.get("slug"),
                "outcomes": outcomes,
                "prices": prices,
                "token_ids": token_ids,
            }

    raise RuntimeError(
        "Event found but no binary market found."
    )


def print_market(event, market):

    slug = event.get("slug", "")

    start_timestamp = get_slug_timestamp(slug)

    if start_timestamp is None:
        raise RuntimeError(
            "Could not extract timestamp from slug."
        )

    end_timestamp = start_timestamp + 300

    start_dt = datetime.fromtimestamp(
        start_timestamp,
        tz=timezone.utc,
    )

    end_dt = datetime.fromtimestamp(
        end_timestamp,
        tz=timezone.utc,
    )

    remaining = max(
        0,
        end_timestamp - int(time.time()),
    )

    print()
    print("=" * 60)
    print("CURRENT POLYMARKET BTC 5-MINUTE MARKET")
    print("=" * 60)

    print(
        f"Title:          {event.get('title')}"
    )

    print(
        f"Event Slug:     {slug}"
    )

    print(
        f"Market:         {market.get('question')}"
    )

    print(
        f"Market Slug:    {market.get('market_slug')}"
    )

    print(
        f"Start UTC:      {start_dt}"
    )

    print(
        f"End UTC:        {end_dt}"
    )

    print(
        f"Seconds left:   {remaining}"
    )

    print()
    print("POLYMARKET OUTCOME PRICES")
    print("-" * 60)

    outcomes = market["outcomes"]
    prices = market["prices"]

    for index, outcome in enumerate(outcomes):

        if index < len(prices):

            try:
                price = float(prices[index])

                print(
                    f"{outcome}: "
                    f"{price:.4f} "
                    f"({price * 100:.2f}%)"
                )

            except (TypeError, ValueError):

                print(
                    f"{outcome}: "
                    f"price unavailable"
                )

        else:

            print(
                f"{outcome}: "
                f"price unavailable"
            )

    print()
    print("CLOB TOKEN IDS")
    print("-" * 60)

    for outcome, token_id in zip(
        outcomes,
        market["token_ids"],
    ):

        print(
            f"{outcome}: {token_id}"
        )

    print()
    print("=" * 60)
    print("PAPER MODE")
    print("NO REAL TRADING")
    print("NO API KEYS")
    print("NO WALLET")
    print("=" * 60)


def run_test():

    print("=" * 60)
    print("POLYMARKET BTC 5-MINUTE MARKET DATA")
    print("=" * 60)

    print()
    print(
        "Connecting to Polymarket public market data..."
    )
    print()

    events = get_active_events()

    print(
        f"Active events received: {len(events)}"
    )

    event = find_current_btc_market(events)

    if event is None:

        print()
        print(
            "NO CURRENT BTC 5-MINUTE MARKET FOUND"
        )

        print()
        print(
            "BTC 5-minute candidates:"
        )

        count = 0

        for candidate in events:

            slug = candidate.get(
                "slug",
                "",
            )

            if get_slug_timestamp(slug):

                print(
                    f"  {slug}"
                )

                count += 1

                if count >= 10:
                    break

        return 0

    market = extract_market(event)

    print_market(
        event,
        market,
    )

    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            run_test()
        )

    except requests.RequestException as exc:

        print()
        print("POLYMARKET REQUEST ERROR")
        print(exc)

        raise SystemExit(1)

    except Exception as exc:

        print()
        print("POLYMARKET DATA ERROR")
        print(exc)

        raise SystemExit(1)
