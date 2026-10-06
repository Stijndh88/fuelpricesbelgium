"""Official maximum prices published daily by FOD Economie (Algemene Directie Energie).

The prices are served by a small table app (embedded in the "Tarif officiel des produits
pétroliers" page on economie.fgov.be) that lists each product with its maximum price in EUR
per litre, VAT included, under the date from which the tariff applies.

Rather than depending on the exact page layout, the parser walks every HTML table row, keeps
rows whose first cell names a tracked product, and takes the first EUR-per-litre looking number
on that row.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import date
from html.parser import HTMLParser

from fuelprices.models import PriceRecord
from fuelprices.products import match_product

SOURCE = "fod-economie"
URL = "https://petrolprices.economie.fgov.be/petrolprices?locale=nl"
USER_AGENT = "fuelpricesbelgium (+https://github.com/Stijndh88/fuelpricesbelgium)"

# 2,0650 / 2.065 / 2,065 € — a plausible pump price in EUR per litre.
_PRICE = re.compile(r"(?<![\d.,])(\d)[.,](\d{2,4})(?![\d.,])")
_DATE_DMY = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


class _TableRows(HTMLParser):
    """Collects the text of every table row as a list of cell strings, plus all page text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.text: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)


def parse_price(text: str) -> float | None:
    match = _PRICE.search(text)
    if not match:
        return None
    value = float(f"{match.group(1)}.{match.group(2)}")
    return value if 0.3 <= value <= 5.0 else None


def parse_date(text: str) -> date | None:
    if m := _DATE_ISO.search(text):
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if m := _DATE_DMY.search(text):
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def parse(html: str, valid_from: date | None = None) -> list[PriceRecord]:
    """Extract one record per tracked product from the FOD Economie price page.

    ``valid_from`` defaults to a date found on the row itself, else the first date on the page.
    """
    parser = _TableRows()
    parser.feed(html)
    page_date = valid_from or parse_date(" ".join(parser.text))

    records: dict = {}
    for row in parser.rows:
        product = match_product(row[0])
        if product is None or product in records:
            continue
        price = next((p for cell in row[1:] if (p := parse_price(cell)) is not None), None)
        if price is None:
            continue
        row_date = valid_from or parse_date(" ".join(row[1:])) or page_date
        if row_date is None:
            raise ValueError("no validity date found on the page; pass valid_from explicitly")
        records[product] = PriceRecord(row_date, product, price, SOURCE)
    if not records:
        raise ValueError("no tracked product prices found on the page; has the layout changed?")
    return list(records.values())


def fetch(url: str = URL, timeout: float = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def fetch_prices(url: str = URL) -> list[PriceRecord]:
    return parse(fetch(url))
