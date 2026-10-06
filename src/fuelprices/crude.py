"""Brent crude oil spot price from FRED (series DCOILBRENTEU, no API key needed).

FRED republishes the EIA daily Brent spot price, usually with a lag of a few
working days, so each run backfills the most recent observations.
"""

from __future__ import annotations

import csv
import io
import urllib.request
from datetime import date

FRED_BRENT_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"


def parse_fred_csv(text: str) -> dict[date, float]:
    """Parse a FRED graph CSV into {day: value}, skipping missing values (".")."""
    reader = csv.reader(io.StringIO(text))
    next(reader, None)  # header: observation_date (or DATE), DCOILBRENTEU
    prices: dict[date, float] = {}
    for record in reader:
        if len(record) < 2 or record[1].strip() in ("", "."):
            continue
        prices[date.fromisoformat(record[0].strip())] = float(record[1])
    return prices


def fetch_brent(since: date, timeout: float = 30) -> dict[date, float]:
    """Download Brent spot prices from FRED for days on or after ``since``."""
    url = f"{FRED_BRENT_URL}&cosd={since.isoformat()}"
    request = urllib.request.Request(url, headers={"User-Agent": "fuelpricesbelgium"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    return {d: v for d, v in parse_fred_csv(text).items() if d >= since}
