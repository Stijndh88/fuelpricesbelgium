"""Export the price history to the JSON file the dashboard reads.

Run with ``python -m fuelprices.export [--db PATH] [--out PATH]``. The dashboard is a
static page (see ``site/``), so this file is all the data it gets: one entry per day
with the official max prices and the Brent price, where known.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fuelprices import history
from fuelprices.history import DailyPrices

DEFAULT_OUT_PATH = Path("site/data/prices.json")


def to_json(rows: list[DailyPrices], now: datetime) -> dict:
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "units": {"diesel": "EUR/L", "e10": "EUR/L", "brent": "USD/bbl"},
        "days": [
            {
                "day": r.day.isoformat(),
                "diesel": r.diesel_max,
                "e10": r.e10_max,
                "brent": r.brent_usd,
            }
            for r in rows
            if r.diesel_max is not None or r.e10_max is not None or r.brent_usd is not None
        ],
    }


def export(conn, out: Path, now: datetime | None = None) -> dict:
    data = to_json(history.all_rows(conn), now or datetime.now(UTC))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=history.DEFAULT_DB_PATH, help="SQLite file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH, help="JSON file to write")
    args = parser.parse_args(argv)
    conn = history.connect(args.db)
    try:
        data = export(conn, args.out)
    finally:
        conn.close()
    print(f"wrote {len(data['days'])} day(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
