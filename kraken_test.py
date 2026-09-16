import time
import requests
from datetime import datetime, timezone


URL = "https://api.kraken.com/0/public/OHLC"

PAIR = "XBTUSD"
INTERVAL = 5


def main():

    print("=" * 60)
    print("KRAKEN BTC 5-MINUTE MARKET DATA TEST")
    print("=" * 60)

    response = requests.get(
        URL,
        params={
            "pair": PAIR,
            "interval": INTERVAL,
        },
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error"):
        raise RuntimeError(
            f"Kraken API error: {data['error']}"
        )

    result = data.get("result", {})

    candles = []

    for key, value in result.items():

        if key != "last" and isinstance(value, list):
            candles = value
            break

    if not candles:
        raise RuntimeError(
            "Kraken returned no OHLC candles."
        )

    candle = candles[-1]

    timestamp = int(candle[0])
    open_price = float(candle[1])
    high_price = float(candle[2])
    low_price = float(candle[3])
    close_price = float(candle[4])

    start = datetime.fromtimestamp(
        timestamp,
        timezone.utc,
    )

    end_timestamp = timestamp + 300

    end = datetime.fromtimestamp(
        end_timestamp,
        timezone.utc,
    )

    seconds_remaining = max(
        0,
        end_timestamp - int(time.time()),
    )

    print()
    print("KRAKEN BTC DATA")
    print("-" * 60)

    print(
        f"Candle start:      {start}"
    )

    print(
        f"Candle end:        {end}"
    )

    print(
        f"Open:              ${open_price:,.2f}"
    )

    print(
        f"High:              ${high_price:,.2f}"
    )

    print(
        f"Low:               ${low_price:,.2f}"
    )

    print(
        f"Close:             ${close_price:,.2f}"
    )

    print(
        f"Seconds remaining: {seconds_remaining}"
    )

    print()
    print("=" * 60)
    print("PUBLIC READ-ONLY DATA")
    print("NO API KEY")
    print("NO WALLET")
    print("NO TRADING")
    print("=" * 60)


if __name__ == "__main__":
    main()
