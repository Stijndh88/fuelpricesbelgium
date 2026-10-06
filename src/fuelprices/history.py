"""Daily price history stored in a SQLite file (one row per day).

Each row holds the official maximum prices that are valid on that day plus
the market inputs that drive them, where they could be sourced. Columns are
nullable so a row can be filled in by several sources over time: an upsert
never overwrites a known value with NULL.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, fields, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

DEFAULT_DB_PATH = Path("data/prices.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_prices (
    day            TEXT PRIMARY KEY,  -- ISO date the prices are valid on
    diesel_max     REAL,              -- official max price diesel B7, EUR/L incl. VAT
    e10_max        REAL,              -- official max price petrol E10 (95), EUR/L incl. VAT
    diesel_product REAL,              -- wholesale product cost diesel, EUR/L (rules input)
    e10_product    REAL,              -- wholesale product cost petrol, EUR/L (rules input)
    brent_usd      REAL,              -- Brent crude front-month future close, USD per barrel
    updated_at     TEXT NOT NULL      -- UTC timestamp of the last write to this row
);
"""

VALUE_COLUMNS = (
    "diesel_max",
    "e10_max",
    "diesel_product",
    "e10_product",
    "brent_usd",
    "ulsd_usd_gal",
    "rbob_usd_gal",
)


@dataclass(frozen=True)
class DailyPrices:
    day: date
    diesel_max: float | None = None
    e10_max: float | None = None
    diesel_product: float | None = None
    e10_product: float | None = None
    brent_usd: float | None = None
    ulsd_usd_gal: float | None = None
    rbob_usd_gal: float | None = None


def connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the database, creating the file and schema if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    # Columns added after the first release: add them to older files.
    existing = {r[1] for r in conn.execute("PRAGMA table_info(daily_prices)")}
    with conn:
        for column in VALUE_COLUMNS:
            if column not in existing:
                conn.execute(f"ALTER TABLE daily_prices ADD COLUMN {column} REAL")
    return conn


def upsert(conn: sqlite3.Connection, row: DailyPrices, now: datetime | None = None) -> None:
    """Insert the row, or merge it into the existing row for that day.

    Values given as None keep whatever the stored row already has. A row whose
    values would not change is left untouched (updated_at included), so a rerun
    leaves the database file byte-identical.
    """
    now = now or datetime.now(UTC)
    values = {c: getattr(row, c) for c in VALUE_COLUMNS}
    merge = ", ".join(f"{c} = COALESCE(excluded.{c}, daily_prices.{c})" for c in VALUE_COLUMNS)
    changed = " OR ".join(
        f"(excluded.{c} IS NOT NULL AND excluded.{c} IS NOT daily_prices.{c})"
        for c in VALUE_COLUMNS
    )
    with conn:
        conn.execute(
            f"""
            INSERT INTO daily_prices (day, {", ".join(VALUE_COLUMNS)}, updated_at)
            VALUES (:day, {", ".join(":" + c for c in VALUE_COLUMNS)}, :updated_at)
            ON CONFLICT(day) DO UPDATE SET {merge}, updated_at = excluded.updated_at
            WHERE {changed}
            """,
            {"day": row.day.isoformat(), "updated_at": now.isoformat(timespec="seconds"), **values},
        )


def fill_forward(conn: sqlite3.Connection, until: date) -> int:
    """Give every day up to ``until`` a max price, carried over from the day before.

    Official max prices stay in force until FOD Economie publishes a new one, so a day
    without a published price (weekends, a missed run) has the previous day's price.
    Only empty cells are filled. Returns the number of days written.
    """
    rows = {r.day: r for r in all_rows(conn)}
    known = sorted(d for d, r in rows.items() if r.diesel_max is not None or r.e10_max is not None)
    if not known:
        return 0
    written = 0
    previous = rows[known[0]]
    day = known[0] + timedelta(days=1)
    while day <= until:
        current = rows.get(day) or DailyPrices(day=day)
        filled = replace(
            current,
            diesel_max=current.diesel_max
            if current.diesel_max is not None
            else previous.diesel_max,
            e10_max=current.e10_max if current.e10_max is not None else previous.e10_max,
        )
        if filled != current:
            upsert(conn, filled)
            written += 1
        previous = filled
        day += timedelta(days=1)
    return written


def get(conn: sqlite3.Connection, day: date) -> DailyPrices | None:
    cur = conn.execute(
        f"SELECT day, {', '.join(VALUE_COLUMNS)} FROM daily_prices WHERE day = ?",
        (day.isoformat(),),
    )
    found = cur.fetchone()
    return _to_row(found) if found else None


def all_rows(conn: sqlite3.Connection) -> list[DailyPrices]:
    cur = conn.execute(f"SELECT day, {', '.join(VALUE_COLUMNS)} FROM daily_prices ORDER BY day")
    return [_to_row(r) for r in cur.fetchall()]


def _to_row(record: tuple) -> DailyPrices:
    names = [f.name for f in fields(DailyPrices)]
    data = dict(zip(names, record, strict=True))
    data["day"] = date.fromisoformat(data["day"])
    return DailyPrices(**data)
