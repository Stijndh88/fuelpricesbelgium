"""Brent crude oil price: daily close of the front-month ICE Brent future (Yahoo ``BZ=F``).

Yahoo's chart endpoint is unofficial but keyless and answers from GitHub Actions, unlike FRED
and EIA's API (FRED blocks the runners, EIA needs a key). The last bar of the day can be an
intraday value; later runs overwrite it with the final close.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, date, datetime

YAHOO_BRENT_URL = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?range=1mo&interval=1d"
USER_AGENT = "fuelpricesbelgium"  # Yahoo answers 429 to browser-like agents without cookies


def parse_yahoo_chart(text: str) -> dict[date, float]:
    """Parse a Yahoo chart response into {day: close}, skipping days without a close."""
    result = json.loads(text)["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    prices: dict[date, float] = {}
    for stamp, close in zip(result.get("timestamp", []), closes, strict=True):
        if close is not None:
            prices[datetime.fromtimestamp(stamp, UTC).date()] = round(close, 2)
    return prices


def fetch_brent(since: date, timeout: float = 30) -> dict[date, float]:
    """Download daily Brent closes for days on or after ``since`` (up to a month back)."""
    request = urllib.request.Request(YAHOO_BRENT_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    return {d: v for d, v in parse_yahoo_chart(text).items() if d >= since}
