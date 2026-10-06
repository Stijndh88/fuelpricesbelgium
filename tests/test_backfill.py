from datetime import date, timedelta

import pytest

from fuelprices import backfill, crude, history
from fuelprices.products import Product
from fuelprices.sources import petrolfed

TODAY = date(2026, 10, 6)


@pytest.fixture
def conn(tmp_path):
    c = history.connect(tmp_path / "prices.sqlite")
    yield c
    c.close()


def test_backfill_stores_every_source(conn, monkeypatch):
    days = [TODAY - timedelta(days=i) for i in range(3, -2, -1)]
    series = {Product.DIESEL_B7: dict.fromkeys(days, 2.4), Product.E10: dict.fromkeys(days, 2.0)}
    monkeypatch.setattr(petrolfed, "fetch", lambda start, end: series)
    monkeypatch.setattr(crude, "fetch_brent", lambda since: {TODAY: 100.0})
    monkeypatch.setattr(
        crude,
        "fetch_product_futures",
        lambda since: {"ulsd_usd_gal": {TODAY: 4.5}, "eur_usd": {TODAY: 1.17}},
    )
    assert backfill.backfill(conn, TODAY - timedelta(days=3), TODAY) == []
    stored = history.get(conn, TODAY)
    assert (stored.diesel_max, stored.e10_max, stored.brent_usd) == (2.4, 2.0, 100.0)
    assert (stored.ulsd_usd_gal, stored.eur_usd) == (4.5, 1.17)
    assert history.get(conn, TODAY + timedelta(days=1)).diesel_max == 2.4


def test_backfill_reports_failed_sources_and_keeps_the_rest(conn, monkeypatch):
    def broken(*_):
        raise OSError("down")

    monkeypatch.setattr(petrolfed, "fetch", broken)
    monkeypatch.setattr(crude, "fetch_brent", lambda since: {TODAY: 100.0})
    monkeypatch.setattr(crude, "fetch_product_futures", broken)
    assert backfill.backfill(conn, TODAY, TODAY) == ["petrolfed", "futures"]
    assert history.get(conn, TODAY).brent_usd == 100.0
