from datetime import UTC, date, datetime

import pytest

from fuelprices import history
from fuelprices.history import DailyPrices


@pytest.fixture
def conn(tmp_path):
    c = history.connect(tmp_path / "data" / "prices.sqlite")
    yield c
    c.close()


def test_connect_creates_file_and_schema(tmp_path):
    path = tmp_path / "nested" / "prices.sqlite"
    history.connect(path).close()
    assert path.exists()
    assert history.all_rows(history.connect(path)) == []


def test_upsert_then_get(conn):
    row = DailyPrices(day=date(2026, 10, 7), diesel_max=2.392, e10_max=2.065)
    history.upsert(conn, row)
    assert history.get(conn, date(2026, 10, 7)) == row
    assert history.get(conn, date(2026, 10, 8)) is None


def test_upsert_is_idempotent(conn):
    row = DailyPrices(day=date(2026, 10, 7), diesel_max=2.392, e10_max=2.065)
    history.upsert(conn, row)
    history.upsert(conn, row)
    assert history.all_rows(conn) == [row]


def test_upsert_merges_columns_without_erasing(conn):
    day = date(2026, 10, 6)
    history.upsert(conn, DailyPrices(day=day, diesel_max=2.432, e10_max=2.065))
    history.upsert(conn, DailyPrices(day=day, brent_usd=99.0))
    assert history.get(conn, day) == DailyPrices(
        day=day, diesel_max=2.432, e10_max=2.065, brent_usd=99.0
    )


def test_upsert_overwrites_with_new_value(conn):
    day = date(2026, 10, 7)
    history.upsert(conn, DailyPrices(day=day, diesel_max=2.432))
    history.upsert(conn, DailyPrices(day=day, diesel_max=2.392))
    assert history.get(conn, day).diesel_max == 2.392


def test_updated_at_is_recorded(conn):
    now = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)
    history.upsert(conn, DailyPrices(day=date(2026, 10, 6), e10_max=2.065), now=now)
    (stamp,) = conn.execute("SELECT updated_at FROM daily_prices").fetchone()
    assert stamp == "2026-10-06T06:00:00+00:00"


def test_all_rows_sorted_by_day(conn):
    for d in (3, 1, 2):
        history.upsert(conn, DailyPrices(day=date(2026, 10, d), e10_max=2.0))
    assert [r.day.day for r in history.all_rows(conn)] == [1, 2, 3]


def test_unchanged_upsert_keeps_updated_at(conn):
    day = date(2026, 10, 6)
    first = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)
    history.upsert(conn, DailyPrices(day=day, e10_max=2.065), now=first)
    history.upsert(conn, DailyPrices(day=day, e10_max=2.065), now=datetime.now(UTC))
    history.upsert(conn, DailyPrices(day=day), now=datetime.now(UTC))
    (stamp,) = conn.execute("SELECT updated_at FROM daily_prices").fetchone()
    assert stamp == "2026-10-06T06:00:00+00:00"


def test_rerun_leaves_file_byte_identical(tmp_path):
    path = tmp_path / "prices.sqlite"
    row = DailyPrices(day=date(2026, 10, 7), diesel_max=2.392, e10_max=2.065, brent_usd=99.0)
    with history.connect(path) as c:
        history.upsert(c, row)
    before = path.read_bytes()
    c = history.connect(path)
    history.upsert(c, row)
    c.close()
    assert path.read_bytes() == before


def test_fill_forward_fills_gaps_up_to_until(conn):
    history.upsert(conn, DailyPrices(day=date(2026, 10, 2), diesel_max=2.432, e10_max=2.065))
    history.upsert(conn, DailyPrices(day=date(2026, 10, 4), brent_usd=100.0))
    history.upsert(conn, DailyPrices(day=date(2026, 10, 5), e10_max=2.07))
    assert history.fill_forward(conn, until=date(2026, 10, 6)) == 4
    assert history.all_rows(conn) == [
        DailyPrices(day=date(2026, 10, 2), diesel_max=2.432, e10_max=2.065),
        DailyPrices(day=date(2026, 10, 3), diesel_max=2.432, e10_max=2.065),
        DailyPrices(day=date(2026, 10, 4), diesel_max=2.432, e10_max=2.065, brent_usd=100.0),
        DailyPrices(day=date(2026, 10, 5), diesel_max=2.432, e10_max=2.07),
        DailyPrices(day=date(2026, 10, 6), diesel_max=2.432, e10_max=2.07),
    ]
    assert history.fill_forward(conn, until=date(2026, 10, 6)) == 0


def test_fill_forward_without_prices_does_nothing(conn):
    history.upsert(conn, DailyPrices(day=date(2026, 10, 4), brent_usd=100.0))
    assert history.fill_forward(conn, until=date(2026, 10, 6)) == 0
    assert len(history.all_rows(conn)) == 1


def test_connect_adds_new_columns_to_an_old_file(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE daily_prices (day TEXT PRIMARY KEY, diesel_max REAL, e10_max REAL,"
        " diesel_product REAL, e10_product REAL, brent_usd REAL, updated_at TEXT NOT NULL)"
    )
    old.execute(
        "INSERT INTO daily_prices VALUES ('2026-10-07', 2.392, 2.065, NULL, NULL, NULL, 'x')"
    )
    old.commit()
    old.close()
    conn = history.connect(path)
    history.upsert(conn, DailyPrices(day=date(2026, 10, 7), ulsd_usd_gal=4.49))
    assert history.get(conn, date(2026, 10, 7)) == DailyPrices(
        day=date(2026, 10, 7), diesel_max=2.392, e10_max=2.065, ulsd_usd_gal=4.49
    )
