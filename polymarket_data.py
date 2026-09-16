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
import time
from datetime import datetime, timezone

import requests


GAMMA_EVENT_BY_SLUG = (
    "https://gamma-api.polymarket.com/events/slug/"
)

TIMEOUT = 10

FIVE_MINUTES = 300


def utc_now():
    return datetime.now(timezone.utc)


def current_5m_start_timestamp():
    """
    Calculate the Unix timestamp of the current
    5-minute UTC window.
    """

    now = int(time.time())

    return now - (now % FIVE_MINUTES)


def current_market_slug():
    start_timestamp = current_5m_start_timestamp()

    return (
        f"btc-updown-5m-{start_timestamp}"
    )


def get_event_by_slug(slug):

    url = (
        GAMMA_EVENT_BY_SLUG
        + slug
    )

    response = requests.get(
        url,
        timeout=TIMEOUT,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json()


def parse_array(value):

    if isinstance(value, str):

        try:
            return json.loads(value)

        except json.JSONDecodeError:

            return []

    return value or []


def extract_market(event):

    markets = event.get(
        "markets",
        [],
    )

    if not markets:

        raise RuntimeError(
            "Event found but contains no markets."
        )

    for market in markets:

        outcomes = parse_array(
            market.get(
                "outcomes",
                "[]",
            )
        )

        prices = parse_array(
            market.get(
                "outcomePrices",
                "[]",
            )
        )

        token_ids = parse_array(
            market.get(
                "clobTokenIds",
                "[]",
            )
        )

        if len(outcomes) >= 2:

            return {
                "question": market.get(
                    "question"
                ),

                "condition_id": market.get(
                    "conditionId"
                ),

                "market_slug": market.get(
                    "slug"
                ),

                "outcomes": outcomes,

                "prices": prices,

                "token_ids": token_ids,
            }

    raise RuntimeError(
        "No binary BTC market found."
    )


def run_test():

    print("=" * 60)
    print(
        "POLYMARKET BTC 5-MINUTE MARKET DATA"
    )
    print("=" * 60)

    print()
    print(
        "Connecting to Polymarket public market data..."
    )
    print()

    start_timestamp = (
        current_5m_start_timestamp()
    )

    end_timestamp = (
        start_timestamp + FIVE_MINUTES
    )

    slug = current_market_slug()

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

    print(
        f"Current UTC:    {utc_now()}"
    )

    print(
        f"5m Start UTC:   {start_dt}"
    )

    print(
        f"5m End UTC:     {end_dt}"
    )

    print(
        f"Seconds left:   {remaining}"
    )

    print()

    print(
        f"Calculated slug:"
    )

    print(
        f"  {slug}"
    )

    print()

    event = get_event_by_slug(
        slug
    )

    if event is None:

        print(
            "CURRENT MARKET NOT FOUND"
        )

        print()
        print(
            "The calculated market slug does not"
        )

        print(
            "exist in Polymarket's public Gamma API."
        )

        print()
        print(
            "PAPER MODE"
        )

        print(
            "NO REAL TRADING"
        )

        print(
            "NO API KEYS"
        )

        print(
            "NO WALLET"
        )

        return 0

    market = extract_market(
        event
    )

    print()
    print("=" * 60)
    print(
        "CURRENT POLYMARKET BTC 5-MINUTE MARKET"
    )
    print("=" * 60)

    print(
        f"Title:          {event.get('title')}"
    )

    print(
        f"Event Slug:     {event.get('slug')}"
    )

    print(
        f"Question:       {market.get('question')}"
    )

    print(
        f"Market Slug:    {market.get('market_slug')}"
    )

    print(
        f"Condition ID:   {market.get('condition_id')}"
    )

    print(
        f"Seconds left:   {remaining}"
    )

    print()
    print(
        "POLYMARKET OUTCOME PRICES"
    )
    print("-" * 60)

    outcomes = market["outcomes"]

    prices = market["prices"]

    for index, outcome in enumerate(
        outcomes
    ):

        if index < len(prices):

            try:

                price = float(
                    prices[index]
                )

                print(
                    f"{outcome}: "
                    f"{price:.4f} "
                    f"({price * 100:.2f}%)"
                )

            except (
                TypeError,
                ValueError,
            ):

                print(
                    f"{outcome}: "
                    "price unavailable"
                )

        else:

            print(
                f"{outcome}: "
                "price unavailable"
            )

    print()
    print(
        "CLOB TOKEN IDS"
    )
    print("-" * 60)

    for outcome, token_id in zip(
        market["outcomes"],
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

    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            run_test()
        )

    except requests.RequestException as exc:

        print()
        print(
            "POLYMARKET REQUEST ERROR"
        )

        print(exc)

        raise SystemExit(1)

    except Exception as exc:

        print()
        print(
            "POLYMARKET DATA ERROR"
        )

        print(exc)

        raise SystemExit(1)
