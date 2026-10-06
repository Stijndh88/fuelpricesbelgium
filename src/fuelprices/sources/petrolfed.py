"""Official maximum prices as published by Energia (petrolfed.be), daily since 2011.

The "Evolutie" chart on petrolfed.be/nl/maximumprijzen/evolutie loads its data from a public JSON
endpoint: one series per product with the max price (EUR/L incl. VAT) for *every calendar day*
in the requested range, including tomorrow's already published price. Unlike the FOD Economie
page, which only lists the tariff valid from the next day, this gives today's price too, and
the whole history back to 2011 (E10 from June 2014).
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date

from fuelprices.models import PriceRecord
from fuelprices.products import Product

SOURCE = "petrolfed"
URL = "https://petrolfed.be/nl/dms_maximumprijs_export/all/{start}/{end}"
USER_AGENT = "fuelpricesbelgium (+https://github.com/Stijndh88/fuelpricesbelgium)"

# taxonomy_tid of the products we track in the JSON series.
PRODUCT_TIDS = {"31": Product.DIESEL_B7, "28": Product.E10}


def parse(text: str) -> dict[Product, dict[date, float]]:
    """Parse the export into {product: {day: max price}} for the tracked products."""
    series: dict[Product, dict[date, float]] = {}
    for item in json.loads(text):
        product = PRODUCT_TIDS.get(str(item.get("taxonomy_tid")))
        if product is None:
            continue
        series[product] = {
            date.fromisoformat(day): float(price)
            for day, price in item["data"].items()
            if price not in (None, "")
        }
    return series


def to_records(series: dict[Product, dict[date, float]]) -> list[PriceRecord]:
    """One record per product and day. Days with the same price as the day before are kept."""
    return [
        PriceRecord(day, product, price, SOURCE)
        for product, prices in series.items()
        for day, price in sorted(prices.items())
    ]


def fetch(start: date, end: date, timeout: float = 60) -> dict[Product, dict[date, float]]:
    """Download the daily max prices from ``start`` to ``end`` (tomorrow is the latest end)."""
    url = URL.format(start=start.isoformat(), end=end.isoformat())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        series = parse(response.read().decode("utf-8"))
    if not series:
        raise ValueError("no diesel or E10 series in the petrolfed export; has the format changed?")
    return series
