import json
from datetime import date, timedelta

import pytest

from fuelprices import advice, history
from fuelprices.history import DailyPrices
from fuelprices.products import Product

MON = date(2026, 10, 5)


def days(start, diesel, brent=None):
    """One row per day from ``start`` with the given diesel max prices (and Brent, if given)."""
    brent = brent or [None] * len(diesel)
    return [
        DailyPrices(day=start + timedelta(days=i), diesel_max=d, e10_max=1.80, brent_usd=b)
        for i, (d, b) in enumerate(zip(diesel, brent, strict=True))
    ]


def test_published_drop_means_wait():
    rows = days(MON, [2.40, 2.37])
    a = advice.advise(Product.DIESEL_B7, rows, MON)
    assert a.action == advice.WAIT
    assert a.basis == "published"
    assert a.expected_change_cents == -3.0
    assert "drops 3.0 cent/L tomorrow" in a.reason


def test_published_rise_means_fill_up():
    a = advice.advise(Product.DIESEL_B7, days(MON, [2.40, 2.42]), MON)
    assert a.action == advice.FILL_UP
    assert a.expected_change_cents == 2.0


def test_tiny_published_change_is_no_difference():
    a = advice.advise(Product.DIESEL_B7, days(MON, [2.400, 2.402]), MON)
    assert a.action == advice.NO_DIFFERENCE
    assert a.basis == "published"


def test_no_price_today():
    a = advice.advise(Product.DIESEL_B7, days(MON + timedelta(days=1), [2.40]), MON)
    assert a.action == advice.NO_DIFFERENCE
    assert a.basis == "none"


def test_brent_fall_since_last_change_means_wait():
    # Price changed on Tue; Brent fell from 80 to 70 USD since then; Fri price not published yet.
    rows = days(MON, [2.40, 2.35, 2.35, 2.35, 2.35], [80, 80, 76, 72, 70])
    friday = MON + timedelta(days=4)
    a = advice.advise(Product.DIESEL_B7, rows, friday)
    assert a.action == advice.WAIT
    assert a.basis == "brent"
    assert a.expected_change_cents < -5
    assert a.next_possible_change == "2026-10-10"
    assert "Brent 80 to 70 USD since 06/10" in a.reason


def test_brent_rise_means_fill_up():
    rows = days(MON, [2.40, 2.35, 2.35, 2.35], [70, 70, 75, 80])
    a = advice.advise(Product.DIESEL_B7, rows, MON + timedelta(days=3))
    assert a.action == advice.FILL_UP


def test_small_brent_move_stays_in_band():
    rows = days(MON, [2.40, 2.35, 2.35, 2.35], [80, 80, 80.5, 81])
    a = advice.advise(Product.DIESEL_B7, rows, MON + timedelta(days=3))
    assert a.action == advice.NO_DIFFERENCE
    assert a.basis == "brent"


def test_stale_brent_is_ignored():
    rows = days(MON, [2.40] + [2.35] * 10, [70] + [None] * 10)
    a = advice.advise(Product.DIESEL_B7, rows, MON + timedelta(days=10))
    assert a.basis == "none"


def test_future_rows_are_ignored():
    # A row two days ahead must not leak into today's advice (matters for the backtest).
    rows = days(MON, [2.40, 2.40, 2.20])
    assert advice.advise(Product.DIESEL_B7, rows, MON).action == advice.NO_DIFFERENCE


def test_weekend_next_possible_change():
    assert advice.next_possible_change(date(2026, 10, 9)) == date(2026, 10, 10)  # Fri
    assert advice.next_possible_change(date(2026, 10, 10)) == date(2026, 10, 13)  # Sat
    assert advice.next_possible_change(date(2026, 10, 11)) == date(2026, 10, 13)  # Sun


def test_backtest_needs_enough_history():
    result = advice.backtest(Product.DIESEL_B7, days(MON, [2.40, 2.37]))
    assert result.windows == 0
    assert "Not enough history" in result.note


def test_backtest_waiting_for_a_drop_saves():
    # A published drop on day 2; waiting from day 1 pays the lower price.
    rows = days(MON, [2.40, 2.30] + [2.30] * 6)
    result = advice.backtest(Product.DIESEL_B7, rows, horizon_days=3)
    assert result.windows == 6
    assert result.saved == 1
    assert result.lost == 0
    assert result.avg_saving_cents > 0


def test_export_and_write_json_is_stable(tmp_path):
    conn = history.connect(tmp_path / "prices.sqlite")
    for row in days(MON, [2.40, 2.37]):
        history.upsert(conn, row)
    data = advice.export(conn, MON)
    assert [a["product"] for a in data["advice"]] == ["diesel_b7", "e10"]
    assert data["advice"][0]["action"] == "wait"
    assert data["caveats"]

    path = tmp_path / "out" / "advice.json"
    assert advice.write_json(path, data)
    assert json.loads(path.read_text())["as_of"] == "2026-10-05"
    assert not advice.write_json(path, data)


def test_brent_conversion():
    assert advice.brent_to_eur_per_litre(110 * advice.LITRES_PER_BARREL / 100) == pytest.approx(1.0)


def test_cli_advise_writes_json(tmp_path):
    from fuelprices import cli

    db = tmp_path / "prices.sqlite"
    conn = history.connect(db)
    for row in days(MON, [2.40, 2.42]):
        history.upsert(conn, row)
    conn.close()
    out = tmp_path / "advice.json"
    cli.main(["advise", "--db", str(db), "--json", str(out), "--date", "2026-10-05"])
    assert json.loads(out.read_text())["advice"][0]["action"] == "fill_up_today"
