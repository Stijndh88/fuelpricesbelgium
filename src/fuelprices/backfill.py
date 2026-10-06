"""Fill the history database with years of past prices, to calibrate the price rules on.

Run with ``python -m fuelprices.backfill --since 2019-01-01``. It downloads the daily official
max prices (petrolfed.be), Brent, the New York diesel and gasoline futures and EUR/USD, and
merges them into the database like the daily job does. Safe to repeat: known values are kept.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from fuelprices import crude, history, update
from fuelprices.history import DailyPrices
from fuelprices.sources import petrolfed

log = logging.getLogger(__name__)


def backfill(conn, since: date, today: date) -> list[str]:
    """Store everything from ``since`` on. Returns the names of the sources that failed."""
    failed = []
    try:
        records = petrolfed.to_records(petrolfed.fetch(since, today + timedelta(days=1)))
        rows = update.to_daily(records)
        for row in rows:
            history.upsert(conn, row)
        log.info("max prices: %d day(s) from %s", len(rows), rows[0].day if rows else "-")
    except Exception:
        log.exception("petrolfed: fetch failed")
        failed.append("petrolfed")

    try:
        brent = crude.fetch_brent(since)
        for day, price in brent.items():
            history.upsert(conn, DailyPrices(day=day, brent_usd=price))
        log.info("brent: %d day(s)", len(brent))
    except Exception:
        log.exception("brent: fetch failed")
        failed.append("brent")

    try:
        for column, prices in crude.fetch_product_futures(since).items():
            for day, price in prices.items():
                history.upsert(conn, DailyPrices(day=day, **{column: price}))
            log.info("%s: %d day(s)", column, len(prices))
    except Exception:
        log.exception("product futures: fetch failed")
        failed.append("futures")

    history.fill_forward(conn, until=today + timedelta(days=1))
    return failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=history.DEFAULT_DB_PATH, help="SQLite file")
    parser.add_argument("--since", type=date.fromisoformat, default=date(2019, 1, 1))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    conn = history.connect(args.db)
    try:
        failed = backfill(conn, args.since, date.today())
    finally:
        conn.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
