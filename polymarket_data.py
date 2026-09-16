"""
Polymarket BTC 5-Minute Market Data

PAPER / READ-ONLY ONLY

- No API keys
- No wallet
- No private keys
- No orders
- No trading

Finds the currently active BTC Up/Down 5-minute
Polymarket market and reads public market prices.
"""

import json
from datetime import datetime, timezone

import requests


GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"
TIMEOUT = 10


def get_current_time():
    return datetime.now(timezone.utc)


def parse_time(value):
    if not value:
        return None

    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def get_active_events():
    """
    Retrieve active, non-closed Polymarket events.
    """

    params = {
        "active": "true",
        "closed": "false",
        "limit": 100,
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


def is_btc_5m_event(event):
    """
    Identify BTC Up/Down 5-minute markets.

    We deliberately use several fields because the exact
    slug can change over time.
    """

    values = [
        str(event.get("slug", "")),
        str(event.get("title", "")),
        str(event.get("ticker", "")),
        str(event.get("description", "")),
        str(event.get("seriesSlug", "")),
    ]

    text = " ".join(values).lower()

    has_btc = "btc" in text or "bitcoin" in text

    has_direction = (
        "up or down" in text
        or "up/down" in text
        or "updown" in text
    )

    has_five_minute = (
        "5m" in text
        or "5-min" in text
        or "5 min" in text
        or "five minute" in text
    )

    return has_btc and has_direction and has_five_minute


def find_current_market(events):
    """
    Find the currently active BTC 5-minute market.
    """

    now = get_current_time()

    candidates = []

    for event in events:

        if not is_btc_5m_event(event):
            continue

        start_value = (
            event.get("startDate")
            or event.get("eventStartTime")
            or event.get("startTime")
        )

        end_value = event.get("endDate")

        if not start_value or not end_value:
            continue

        try:
            start_time = parse_time(start_value)
            end_time = parse_time(end_value)
        except Exception:
            continue

        if start_time <= now < end_time:
            candidates.append(event)

    if not candidates:
        return None

    candidates.sort(
        key=lambda event: parse_time(event["endDate"])
    )

    return candidates[0]


def parse_array(value):
    """
    Polymarket frequently returns arrays as JSON strings.
    """

    if isinstance(value, str):
        return json.loads(value)

    return value


def extract_market(event):
    """
    Extract the first suitable market from the event.
    """

    markets = event.get("markets", [])

    if not markets:
        raise RuntimeError(
            "BTC event found, but it contains no markets."
        )

    for market in markets:

        outcomes = parse_array(
            market.get("outcomes", "[]")
        )

        prices = parse_array(
            market.get("outcomePrices", "[]")
        )

        if len(outcomes) >= 2:

            return {
                "event_title": event.get("title"),
                "event_slug": event.get("slug"),
                "event_start": (
                    event.get("startDate")
                    or event.get("eventStartTime")
                ),
                "event_end": event.get("endDate"),
                "question": market.get("question"),
                "condition_id": market.get("conditionId"),
                "market_slug": market.get("slug"),
                "outcomes": outcomes,
                "prices": prices,
                "clob_token_ids": parse_array(
                    market.get("clobTokenIds", "[]")
                ),
            }

    raise RuntimeError(
        "BTC event found, but no binary market was found."
    )


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
    print(
        "Connecting to Polymarket public market data..."
    )
    print()

    events = get_active_events()

    print(
        f"Active events received: {len(events)}"
    )

    event = find_current_market(events)

    if event is None:

        print()
        print(
            "NO CURRENT BTC 5-MINUTE MARKET FOUND"
        )

        print()
        print(
            "BTC-related candidates found:"
        )

        count = 0

        for candidate in events:

            text = " ".join(
                [
                    str(candidate.get("slug", "")),
                    str(candidate.get("title", "")),
                    str(candidate.get("ticker", "")),
                ]
            ).lower()

            if (
                "btc" in text
                or "bitcoin" in text
            ):
                print(
                    f"  - {candidate.get('slug')}"
                )

                print(
                    f"    {candidate.get('title')}"
                )

                count += 1

                if count >= 10:
                    break

        return 0

    market = extract_market(event)

    remaining = seconds_remaining(
        market["event_end"]
    )

    print()
    print("CURRENT MARKET")
    print("-" * 60)

    print(
        f"Event:          {market['event_title']}"
    )

    print(
        f"Event Slug:     {market['event_slug']}"
    )

    print(
        f"Market:         {market['question']}"
    )

    print(
        f"Market Slug:    {market['market_slug']}"
    )

    print(
        f"Condition ID:   {market['condition_id']}"
    )

    print(
        f"Start:          {market['event_start']}"
    )

    print(
        f"End:            {market['event_end']}"
    )

    print(
        f"Seconds left:   {remaining:.1f}"
    )

    print()
    print("POLYMARKET OUTCOME PRICES")
    print("-" * 60)

    outcomes = market["outcomes"]
    prices = market["prices"]

    for index, outcome in enumerate(outcomes):

        price = None

        if index < len(prices):
            try:
                price = float(prices[index])
            except Exception:
                price = None

        if price is None:
            print(
                f"{outcome}: price unavailable"
            )
        else:
            print(
                f"{outcome}: {price:.4f} "
                f"({price * 100:.2f}%)"
            )

    print()
    print("CLOB TOKEN IDS")
    print("-" * 60)

    for outcome, token_id in zip(
        market["outcomes"],
        market["clob_token_ids"],
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
