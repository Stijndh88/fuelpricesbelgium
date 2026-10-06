from datetime import date, timedelta
from pathlib import Path

import pytest

from fuelprices import history, update
from fuelprices.history import DailyPrices
from fuelprices.models import PriceRecord
from fuelprices.products import Product

TODAY = date(2026, 10, 6)
TOMORROW = TODAY + timedelta(days=1)
FIXTURE = Path(__file__).parent / "fixtures" / "fod_sample.html"


@pytest.fixture
def conn(tmp_path):
    c = history.connect(tmp_path / "prices.sqlite")
    yield c
    c.close()


def official():
    return [
        PriceRecord(TODAY, Product.DIESEL_B7, 2.432, "test"),
        PriceRecord(TODAY, Product.E10, 2.065, "test"),
        PriceRecord(TODAY, Product.LPG, 0.861, "test"),
        PriceRecord(TOMORROW, Product.DIESEL_B7, 2.392, "test"),
    ]


def brent(since):
    assert since == TODAY - timedelta(days=update.BRENT_LOOKBACK_DAYS)
    return {date(2026, 10, 2): 101.0, TODAY: 99.0}


def broken(*_):
    raise OSError("source down")


def test_to_daily_keeps_diesel_and_e10_per_day():
    assert update.to_daily(official()) == [
        DailyPrices(day=TODAY, diesel_max=2.432, e10_max=2.065),
        DailyPrices(day=TOMORROW, diesel_max=2.392),
    ]


def test_run_stores_all_sources_and_fills_forward(conn):
    assert update.run(conn, TODAY, fetch_max=official, fetch_brent=brent) == []
    assert history.all_rows(conn) == [
        DailyPrices(day=date(2026, 10, 2), brent_usd=101.0),
        DailyPrices(day=TODAY, diesel_max=2.432, e10_max=2.065, brent_usd=99.0),
        # E10 did not change, so tomorrow keeps today's price.
        DailyPrices(day=TOMORROW, diesel_max=2.392, e10_max=2.065),
    ]


def test_run_twice_changes_nothing(conn):
    update.run(conn, TODAY, fetch_max=official, fetch_brent=brent)
    first = history.all_rows(conn)
    update.run(conn, TODAY, fetch_max=official, fetch_brent=brent)
    assert history.all_rows(conn) == first


def test_missed_days_get_the_last_known_price(conn):
    update.run(conn, TODAY, fetch_max=official, fetch_brent=brent)
    later = TODAY + timedelta(days=4)
    update.run(conn, later, fetch_max=broken, fetch_brent=lambda _: {})
    assert history.get(conn, later) == DailyPrices(day=later, diesel_max=2.392, e10_max=2.065)


def test_one_failing_source_keeps_the_other(conn):
    assert update.run(conn, TODAY, fetch_max=official, fetch_brent=broken) == ["brent"]
    assert history.get(conn, TODAY).diesel_max == 2.432

    assert update.run(conn, TODAY, fetch_max=broken, fetch_brent=brent) == ["max_prices"]
    assert history.get(conn, TODAY).brent_usd == 99.0


def test_no_diesel_or_e10_counts_as_failure(conn):
    lpg_only = [PriceRecord(TODAY, Product.LPG, 0.861, "test")]
    assert update.run(conn, TODAY, fetch_max=lambda: lpg_only, fetch_brent=brent) == ["max_prices"]


def test_main_with_saved_page(tmp_path, monkeypatch):
    db = tmp_path / "prices.sqlite"
    monkeypatch.setattr(update.crude, "fetch_brent", broken)
    assert update.main(["--db", str(db), "--html", str(FIXTURE)]) == 0
    stored = history.get(history.connect(db), date(2026, 10, 7))
    assert (stored.diesel_max, stored.e10_max) == (2.392, 2.065)


def test_main_fails_when_max_prices_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(update.fod, "fetch_prices", broken)
    monkeypatch.setattr(update.crude, "fetch_brent", broken)
    assert update.main(["--db", str(tmp_path / "prices.sqlite")]) == 1
