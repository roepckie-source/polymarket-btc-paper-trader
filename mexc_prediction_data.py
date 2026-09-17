"""
MEXC BTC Up/Down Prediction Market
==================================

PAPER-TRADING DATA ADAPTER ONLY

This module does NOT:
- create API keys
- place orders
- cancel orders
- access private account data
- use real money

It attempts to read the public MEXC prediction-market webpage
and extract the currently displayed BTC 5-minute market data.

If MEXC changes its frontend/API structure, the adapter will
fail safely instead of inventing market data.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests


# ============================================================
# CONFIG
# ============================================================

MEXC_PREDICTION_URL = (
    "https://prediction.mexc.com/prediction-markets/up-down"
)

BTC_5M_PAGE_URL = (
    "https://prediction.mexc.com/prediction-markets/up-down"
)

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# RESULT OBJECT
# ============================================================

@dataclass
class MEXCPredictionMarket:
    exchange: str
    market_type: str

    market_id: Optional[str]
    market_slug: Optional[str]
    market_url: Optional[str]

    title: Optional[str]

    btc_baseline: Optional[float]
    btc_current: Optional[float]

    up_price: Optional[float]
    down_price: Optional[float]

    start_timestamp: Optional[int]
    end_timestamp: Optional[int]

    seconds_remaining: Optional[int]

    source: str
    timestamp_utc: str

    raw_data_found: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# HTTP
# ============================================================

def fetch_page(url: str) -> str:
    """
    Download the public MEXC prediction page.

    No authentication.
    No API key.
    No trading.
    """

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


# ============================================================
# GENERIC EXTRACTION HELPERS
# ============================================================

def extract_json_objects(html: str):
    """
    Try to locate JSON-looking objects inside the HTML.

    MEXC may embed application state in:
    - script tags
    - __NEXT_DATA__
    - serialized frontend state
    - JSON blobs

    We do not assume a specific framework.
    """

    results = []

    # --------------------------------------------------------
    # Script contents
    # --------------------------------------------------------

    script_pattern = re.compile(
        r"<script[^>]*>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )

    for match in script_pattern.finditer(html):
        content = match.group(1).strip()

        if not content:
            continue

        # Direct JSON
        if content.startswith("{") or content.startswith("["):
            try:
                results.append(json.loads(content))
            except Exception:
                pass

        # __NEXT_DATA__ style
        if "__NEXT_DATA__" in match.group(0):
            try:
                results.append(json.loads(content))
            except Exception:
                pass

    return results


def find_numbers_near_keywords(
    text: str,
    keywords,
):
    """
    Search for numeric values close to a keyword.

    This is deliberately conservative.
    """

    values = []

    for keyword in keywords:

        pattern = re.compile(
            rf"{re.escape(keyword)}"
            rf".{{0,150}}?"
            rf"(-?\d+(?:\.\d+)?)",
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(text):
            try:
                values.append(float(match.group(1)))
            except Exception:
                continue

    return values


def find_first_number(
    text: str,
    keywords,
) -> Optional[float]:

    values = find_numbers_near_keywords(
        text,
        keywords,
    )

    if not values:
        return None

    return values[0]


def find_timestamp(
    text: str,
    keywords,
) -> Optional[int]:

    # --------------------------------------------------------
    # 10-digit Unix timestamps
    # --------------------------------------------------------

    for keyword in keywords:

        pattern = re.compile(
            rf"{re.escape(keyword)}"
            rf".{{0,150}}?"
            rf"(1\d{{9}}|2\d{{9}})",
            re.IGNORECASE | re.DOTALL,
        )

        match = pattern.search(text)

        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass

    return None


# ============================================================
# MARKET SLUG
# ============================================================

def find_btc_5m_slug(
    html: str,
) -> Optional[str]:

    patterns = [

        # Example:
        # btc-updown-5m-1789637400
        r"btc-updown-5m-\d+",

        # More generic MEXC prediction slug
        r"btc-5min-[0-9\-.]+-target",

        # URL encoded
        r"btc%2Dupdown%2D5m%2D\d+",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE,
        )

        if match:
            return match.group(0)

    return None


# ============================================================
# MARKET ID
# ============================================================

def find_market_id(
    html: str,
) -> Optional[str]:

    # MEXC prediction market IDs seen in public pages
    # are numeric IDs such as:
    #
    # 3000234244505

    patterns = [

        r'"marketId"\s*:\s*"(\d+)"',
        r'"market_id"\s*:\s*"(\d+)"',
        r'"id"\s*:\s*"?(300\d{9,})"?',
        r"/(\d{13,})",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE,
        )

        if match:

            candidate = match.group(1)

            if candidate.isdigit():
                return candidate

    return None


# ============================================================
# TITLE
# ============================================================

def find_title(
    html: str,
) -> Optional[str]:

    patterns = [

        r"BTC\s+5min\s*·[^<\n]+",

        r"Bitcoin[^<\n]{0,150}",

        r"BTC[^<\n]{0,150}target",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE,
        )

        if match:

            title = match.group(0)

            title = re.sub(
                r"\s+",
                " ",
                title,
            ).strip()

            return title[:250]

    return None


# ============================================================
# UP / DOWN PRICE
# ============================================================

def find_up_down_prices(
    html: str,
):

    up = None
    down = None

    # --------------------------------------------------------
    # Common JSON names
    # --------------------------------------------------------

    up_keywords = [
        "upPrice",
        "up_price",
        "Up Price",
        '"Up"',
        "Trade Up",
    ]

    down_keywords = [
        "downPrice",
        "down_price",
        "Down Price",
        '"Down"',
        "Trade Down",
    ]

    up = find_first_number(
        html,
        up_keywords,
    )

    down = find_first_number(
        html,
        down_keywords,
    )

    # --------------------------------------------------------
    # Try probability / price patterns
    # --------------------------------------------------------

    if up is None:

        pattern = re.compile(
            r"Up.{0,100}?"
            r"(0?\.\d+|1(?:\.0+)?)",
            re.IGNORECASE | re.DOTALL,
        )

        match = pattern.search(html)

        if match:

            try:
                up = float(match.group(1))
            except Exception:
                pass

    if down is None:

        pattern = re.compile(
            r"Down.{0,100}?"
            r"(0?\.\d+|1(?:\.0+)?)",
            re.IGNORECASE | re.DOTALL,
        )

        match = pattern.search(html)

        if match:

            try:
                down = float(match.group(1))
            except Exception:
                pass

    # --------------------------------------------------------
    # Sanity checks
    # --------------------------------------------------------

    if up is not None:

        if not 0 <= up <= 1:
            up = None

    if down is not None:

        if not 0 <= down <= 1:
            down = None

    return up, down


# ============================================================
# BASELINE / CURRENT BTC PRICE
# ============================================================

def find_btc_prices(
    html: str,
):

    baseline = None
    current = None

    baseline_keywords = [
        "baselinePrice",
        "baseline_price",
        "Baseline Price",
        "baseline",
        "targetPrice",
        "target_price",
    ]

    current_keywords = [
        "realTimeIndex",
        "real_time_index",
        "Real-Time Index",
        "indexPrice",
        "index_price",
        "currentPrice",
        "current_price",
    ]

    baseline = find_first_number(
        html,
        baseline_keywords,
    )

    current = find_first_number(
        html,
        current_keywords,
    )

    # --------------------------------------------------------
    # Sanity checks for BTC/USD
    # --------------------------------------------------------

    if baseline is not None:

        if not 10_000 <= baseline <= 1_000_000:
            baseline = None

    if current is not None:

        if not 10_000 <= current <= 1_000_000:
            current = None

    return baseline, current


# ============================================================
# TIME DATA
# ============================================================

def find_start_end(
    html: str,
):

    start = find_timestamp(
        html,
        [
            "startTime",
            "start_time",
            "startTimestamp",
            "start_timestamp",
            "windowStart",
            "window_start",
        ],
    )

    end = find_timestamp(
        html,
        [
            "endTime",
            "end_time",
            "endTimestamp",
            "end_timestamp",
            "windowEnd",
            "window_end",
        ],
    )

    return start, end


# ============================================================
# MAIN PARSER
# ============================================================

def parse_market_page(
    html: str,
) -> MEXCPredictionMarket:

    now = datetime.now(
        timezone.utc
    )

    slug = find_btc_5m_slug(
        html
    )

    market_id = find_market_id(
        html
    )

    title = find_title(
        html
    )

    up_price, down_price = find_up_down_prices(
        html
    )

    baseline, current = find_btc_prices(
        html
    )

    start_timestamp, end_timestamp = find_start_end(
        html
    )

    seconds_remaining = None

    if end_timestamp is not None:

        seconds_remaining = max(
            0,
            int(
                end_timestamp
                - now.timestamp()
            ),
        )

    market_url = None

    if slug:

        market_url = (
            MEXC_PREDICTION_URL
            + "/"
            + slug
        )

    raw_data_found = any(
        value is not None
        for value in [
            slug,
            market_id,
            title,
            up_price,
            down_price,
            baseline,
            current,
            start_timestamp,
            end_timestamp,
        ]
    )

    return MEXCPredictionMarket(
        exchange="MEXC",
        market_type="BTC_UP_DOWN_5M",

        market_id=market_id,
        market_slug=slug,
        market_url=market_url,

        title=title,

        btc_baseline=baseline,
        btc_current=current,

        up_price=up_price,
        down_price=down_price,

        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,

        seconds_remaining=seconds_remaining,

        source="MEXC public prediction page",
        timestamp_utc=now.isoformat(),

        raw_data_found=raw_data_found,
    )


# ============================================================
# PUBLIC FUNCTION USED BY OUR BOT
# ============================================================

def get_market_data() -> Dict[str, Any]:

    html = fetch_page(
        BTC_5M_PAGE_URL
    )

    market = parse_market_page(
        html
    )

    return market.to_dict()


# ============================================================
# TEST
# ============================================================

def print_market_data(
    data: Dict[str, Any],
):

    print()
    print("=" * 60)
    print("MEXC BTC 5M UP/DOWN PAPER DATA")
    print("=" * 60)

    print()

    print("Exchange:          ", data.get("exchange"))
    print("Market Type:       ", data.get("market_type"))
    print("Market ID:         ", data.get("market_id"))
    print("Market Slug:       ", data.get("market_slug"))
    print("Title:             ", data.get("title"))

    print()

    print(
        "BTC Baseline:      ",
        data.get("btc_baseline"),
    )

    print(
        "BTC Current:       ",
        data.get("btc_current"),
    )

    print()

    print(
        "UP Price:          ",
        data.get("up_price"),
    )

    print(
        "DOWN Price:        ",
        data.get("down_price"),
    )

    print()

    print(
        "Start Timestamp:   ",
        data.get("start_timestamp"),
    )

    print(
        "End Timestamp:     ",
        data.get("end_timestamp"),
    )

    print(
        "Seconds Remaining: ",
        data.get("seconds_remaining"),
    )

    print()

    print(
        "Source:            ",
        data.get("source"),
    )

    print(
        "Raw Data Found:    ",
        data.get("raw_data_found"),
    )

    print()

    print("=" * 60)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("MEXC BTC 5M DATA TEST")
    print("=" * 60)

    print()
    print("PAPER ONLY")
    print("NO API KEY")
    print("NO WALLET")
    print("NO ORDERS")
    print("NO REAL MONEY")
    print()

    try:

        data = get_market_data()

        print_market_data(
            data
        )

        print()

        if not data["raw_data_found"]:

            print(
                "WARNING:"
            )

            print(
                "No usable MEXC market data "
                "was found in the public page."
            )

            print(
                "The adapter will NOT invent "
                "any values."
            )

        else:

            print(
                "MEXC PAGE ACCESS: PASS"
            )

            if data.get("up_price") is not None:

                print(
                    "UP PRICE: PASS"
                )

            else:

                print(
                    "UP PRICE: NOT FOUND"
                )

            if data.get("down_price") is not None:

                print(
                    "DOWN PRICE: PASS"
                )

            else:

                print(
                    "DOWN PRICE: NOT FOUND"
                )

            if data.get("btc_baseline") is not None:

                print(
                    "BASELINE: PASS"
                )

            else:

                print(
                    "BASELINE: NOT FOUND"
                )

            if data.get("seconds_remaining") is not None:

                print(
                    "COUNTDOWN: PASS"
                )

            else:

                print(
                    "COUNTDOWN: NOT FOUND"
                )

    except requests.RequestException as exc:

        print()
        print(
            "MEXC HTTP ERROR:"
        )

        print(
            str(exc)
        )

    except Exception as exc:

        print()
        print(
            "MEXC TEST ERROR:"
        )

        print(
            type(exc).__name__,
            str(exc),
        )

    print()
    print(
        "TEST COMPLETE"
    )
