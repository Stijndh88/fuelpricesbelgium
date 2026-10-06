"""Daily market prices from Yahoo Finance: Brent crude and US diesel and gasoline futures.

* Brent: front-month ICE Brent future (``BZ=F``), USD per barrel.
* Diesel: front-month NYMEX ULSD (New York Harbor ultra-low-sulphur diesel) future (``HO=F``),
  USD per gallon. The European benchmark, ICE low-sulphur gasoil, has no free keyless source;
  ULSD trades on the same diesel market and moves with it.
* Petrol: front-month NYMEX RBOB gasoline future (``RB=F``), USD per gallon.
* The EUR/USD rate (``EURUSD=X``), to turn those into EUR.

Yahoo's chart endpoint is unofficial but keyless and answers from GitHub Actions, unlike FRED
and EIA's API (FRED blocks the runners, EIA needs a key). The last bar of the day can be an
intraday value; later runs overwrite it with the final close.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, date, datetime

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{span}&interval=1d"
RECENT_SPAN = "range=1mo"
RECENT_DAYS = 25  # a "1mo" request covers at least this many days
BRENT = "BZ=F"
ULSD = "HO=F"
RBOB = "RB=F"
EURUSD = "EURUSD=X"
YAHOO_BRENT_URL = YAHOO_CHART_URL.format(symbol=BRENT, span=RECENT_SPAN)
USER_AGENT = "fuelpricesbelgium"  # Yahoo answers 429 to browser-like agents without cookies


def parse_yahoo_chart(text: str, digits: int = 2) -> dict[date, float]:
    """Parse a Yahoo chart response into {day: close}, skipping days without a close."""
    result = json.loads(text)["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    prices: dict[date, float] = {}
    for stamp, close in zip(result.get("timestamp", []), closes, strict=True):
        if close is not None:
            prices[datetime.fromtimestamp(stamp, UTC).date()] = round(close, digits)
    return prices


def fetch_yahoo(
    symbol: str, since: date, digits: int = 2, timeout: float = 30
) -> dict[date, float]:
    """Download daily closes of ``symbol`` for days on or after ``since``.

    The daily job asks for the last month; a backfill from further back asks for explicit dates.
    """
    if (date.today() - since).days <= RECENT_DAYS:
        span = RECENT_SPAN
    else:
        start = int(datetime(since.year, since.month, since.day, tzinfo=UTC).timestamp())
        span = f"period1={start}&period2={int(datetime.now(UTC).timestamp()) + 86400}"
    url = YAHOO_CHART_URL.format(symbol=symbol, span=span)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    return {d: v for d, v in parse_yahoo_chart(text, digits).items() if d >= since}


def fetch_brent(since: date, timeout: float = 30) -> dict[date, float]:
    """Daily Brent closes in USD per barrel."""
    return fetch_yahoo(BRENT, since, timeout=timeout)


def fetch_product_futures(since: date, timeout: float = 30) -> dict[str, dict[date, float]]:
    """Daily ULSD and RBOB closes (USD per gallon) and EUR/USD, keyed by history column."""
    return {
        "ulsd_usd_gal": fetch_yahoo(ULSD, since, digits=4, timeout=timeout),
        "rbob_usd_gal": fetch_yahoo(RBOB, since, digits=4, timeout=timeout),
        "eur_usd": fetch_yahoo(EURUSD, since, digits=5, timeout=timeout),
    }
