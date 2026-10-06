"""Daily update job: fetch the latest prices and merge them into the history database.

Run with ``python -m fuelprices.update [--db PATH] [--html PAGE]``. Each source is fetched
independently, so one source being down still stores what the others return. The job is
idempotent: running it again without new prices leaves the database file unchanged.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from pathlib import Path

from fuelprices import crude, history
from fuelprices.history import DailyPrices
from fuelprices.models import PriceRecord
from fuelprices.products import Product
from fuelprices.sources import fod

log = logging.getLogger(__name__)

BRENT_LOOKBACK_DAYS = 14

# Which history column each tracked product's official max price goes into.
MAX_PRICE_COLUMNS = {Product.DIESEL_B7: "diesel_max", Product.E10: "e10_max"}

MaxPriceFetcher = Callable[[], Iterable[PriceRecord]]
BrentFetcher = Callable[[date], dict[date, float]]


def to_daily(records: Iterable[PriceRecord]) -> list[DailyPrices]:
    """Group official price records into one DailyPrices row per ``valid_from`` day."""
    by_day: dict[date, dict[str, float]] = {}
    for record in records:
        column = MAX_PRICE_COLUMNS.get(record.product)
        if column:
            by_day.setdefault(record.valid_from, {})[column] = record.price_eur_per_litre
    return [DailyPrices(day=day, **values) for day, values in sorted(by_day.items())]


def run(
    conn,
    today: date,
    fetch_max: MaxPriceFetcher | None = None,
    fetch_brent: BrentFetcher | None = None,
) -> list[str]:
    """Fetch every source and store the results. Returns the names of failed sources."""
    fetch_max = fetch_max or fod.fetch_prices
    fetch_brent = fetch_brent or crude.fetch_brent
    failed = []

    try:
        rows = to_daily(fetch_max())
        if not rows:
            raise ValueError("no diesel or E10 price in the official prices")
    except Exception:
        log.exception("official max prices: fetch failed")
        failed.append("max_prices")
        rows = []
    for row in rows:
        history.upsert(conn, row)
        log.info(
            "official max prices from %s: diesel %s, E10 %s", row.day, row.diesel_max, row.e10_max
        )

    try:
        brent = fetch_brent(today - timedelta(days=BRENT_LOOKBACK_DAYS))
    except Exception:
        log.exception("brent: fetch failed")
        failed.append("brent")
    else:
        for day, price in brent.items():
            history.upsert(conn, DailyPrices(day=day, brent_usd=price))
        log.info("brent: %d day(s) since %s", len(brent), min(brent, default="-"))

    # Carry max prices over to days without a publication, up to the last day they are known for.
    history.fill_forward(conn, until=max([today, *(r.day for r in rows)]))
    return failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=history.DEFAULT_DB_PATH, help="SQLite file")
    parser.add_argument("--html", type=Path, help="parse a saved FOD Economie page instead")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    fetch_max = None
    if args.html:
        html = args.html.read_text(encoding="utf-8")

        def fetch_max():
            return fod.parse(html)

    conn = history.connect(args.db)
    try:
        failed = run(conn, date.today(), fetch_max=fetch_max)
    finally:
        conn.close()
    # The official max prices are the point of the job; a missing Brent value is tolerated.
    return 1 if "max_prices" in failed else 0


if __name__ == "__main__":
    sys.exit(main())
