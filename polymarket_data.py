"""
Polymarket BTC 5-Minute Market Data

PAPER / READ-ONLY ONLY

- No API keys
- No wallet
- No private keys
- No orders
- No trading

Finds the currently active BTC Up/Down 5-minute
Polymarket market and reads the public market prices.
"""

import json
import time
from datetime import datetime, timezone

import requests


GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"
CLOB_BOOK_URL = "https://clob.polymarket.com/book"

SERIES_SLUG = "btc-up-or-down-5m"
TIMEOUT = 10


def get_current_time():
    return datetime.now(timezone.utc)


def get_events():
    params = {
        "series_slug": SERIES_SLUG,
        "closed": "false",
        "limit": 500,
        "order": "endDate",
        "ascending": "true",
    }

    response = requests.get(
        GAMMA_EVENTS_URL,
        params=params,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def parse_time(value):
    if not value:
        return None

    value = value.replace("Z", "+00:00")

    return datetime.fromisoformat(value)


def find_current_market(events):
    now = get_current_time()

    for event in events:
        start_value = event.get("eventStartTime")
        end_value = event.get("endDate")

        if not start_value or not end_value:
            continue

        try:
            start_time = parse_time(start_value)
            end_time = parse_time(end_value)
        except ValueError:
            continue

        if start_time <= now < end_time:
            return event

    return None


def get_market_info(event):
    markets = event.get("markets", [])

    if not markets:
        raise RuntimeError("Event contains no market data.")

    market = markets[0]

    outcomes_raw = market.get("outcomes", "[]")
    token_ids_raw = market.get("clobTokenIds", "[]")

    if isinstance(outcomes_raw, str):
        outcomes = json.loads(outcomes_raw)
    else:
        outcomes = outcomes_raw

    if isinstance(token_ids_raw, str):
        token_ids = json.loads(token_ids_raw)
    else:
        token_ids = token_ids_raw

    if len(outcomes) < 2 or len(token_ids) < 2:
        raise RuntimeError(
            "Could not find both UP and DOWN token IDs."
        )

    result = {
        "condition_id": market.get("conditionId"),
        "question": market.get("question"),
        "slug": event.get("slug"),
        "title": event.get("title"),
        "event_start": event.get("eventStartTime"),
        "end_date": event.get("endDate"),
        "outcomes": outcomes,
        "token_ids": token_ids,
    }

    return result


def get_order_book(token_id):
    response = requests.get(
        CLOB_BOOK_URL,
        params={"token_id": token_id},
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def get_best_prices(order_book):
    bids = order_book.get("bids", [])
    asks = order_book.get("asks", [])

    best_bid = None
    best_ask = None

    if bids:
        best_bid = max(
            float(level["price"])
            for level in bids
            if "price" in level
        )

    if asks:
        best_ask = min(
            float(level["price"])
            for level in asks
            if "price" in level
        )

    return best_bid, best_ask


def seconds_remaining(end_date):
    end_time = parse_time(end_date)
    now = get_current_time()

    return max(
        0.0,
        (end_time - now).total_seconds(),
    )


def run_test():
    print("=" * 60)
    print("POLYMARKET BTC 5-MINUTE MARKET DATA")
    print("=" * 60)

    print()
    print("Connecting to Polymarket public market data...")
    print()

    events = get_events()

    print(f"Markets received: {len(events)}")

    event = find_current_market(events)

    if event is None:
        print()
        print("NO CURRENT BTC 5-MINUTE MARKET FOUND")
        print()
        return 0

    market = get_market_info(event)

    print()
    print("CURRENT MARKET")
    print("-" * 60)

    print(f"Title:          {market['title']}")
    print(f"Slug:           {market['slug']}")
    print(f"Condition ID:   {market['condition_id']}")
    print(f"Start:          {market['event_start']}")
    print(f"End:            {market['end_date']}")

    remaining = seconds_remaining(market["end_date"])

    print(f"Seconds left:   {remaining:.1f}")

    print()
    print("POLYMARKET PRICES")
    print("-" * 60)

    for outcome, token_id in zip(
        market["outcomes"],
        market["token_ids"],
    ):
        book = get_order_book(token_id)

        best_bid, best_ask = get_best_prices(book)

        print(f"{outcome}:")
        print(f"  Best Bid:     {best_bid}")
        print(f"  Best Ask:     {best_ask}")
        print(f"  Token ID:     {token_id}")
        print()

    print("=" * 60)
    print("PAPER MODE")
    print("NO REAL TRADING")
    print("NO API KEYS")
    print("NO WALLET")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_test())

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
