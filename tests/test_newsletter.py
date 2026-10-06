from datetime import date

from fuelprices import history, newsletter

HEADER = (
    "date,diesel_now,e10_now,diesel_next,e10_next,next_effective,diesel_pred_dir,diesel_pred_ct,"
    "diesel_pred_day,e10_pred_dir,e10_pred_ct,e10_pred_day,diesel_product_eur_per_1000l,"
    "e10_product_eur_per_1000l,crude_usd\n"
)
ROWS = [
    # Monday: a diesel rise is forecast by Wednesday, E10 is announced down for Tuesday.
    "2026-01-05,2.000,1.800,,1.750,2026-01-06,up,3-5,2026-01-07,,,,1100,,90",
    "2026-01-06,2.000,1.750,,,,,,,,,,,,",
    "2026-01-07,2.040,1.750,,,,,,,,,,,,",
    # A later forecast that did not come true.
    "2026-01-08,2.040,1.750,,,,down,,2026-01-09,,,,,,",
    "2026-01-09,2.040,1.750,,,,,,,,,,,,",
]


def _write(tmp_path):
    path = tmp_path / "n.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return path


def test_load_parses_forecast_and_range(tmp_path):
    issues = newsletter.load(_write(tmp_path))
    first = issues[0]
    assert first.day == date(2026, 1, 5)
    assert first.next_price["e10"] == 1.75
    assert first.next_effective == date(2026, 1, 6)
    assert first.forecast["diesel"] == newsletter.Forecast("up", 4.0, date(2026, 1, 7))
    assert first.forecast["e10"] is None


def test_daily_max_prices_only_fills_between_equal_points(tmp_path):
    issues = newsletter.load(_write(tmp_path))
    diesel = newsletter.daily_max_prices(issues, "diesel")
    # 5 and 6 January are both 2.000; the change to 2.040 happened on the 7th at the latest.
    assert diesel[date(2026, 1, 6)] == 2.0
    assert diesel[date(2026, 1, 8)] == 2.04
    e10 = newsletter.daily_max_prices(issues, "e10")
    assert e10[date(2026, 1, 6)] == 1.75
    # 5 January has the stated E10 price; the next-day price differs, so nothing is carried over.
    assert e10[date(2026, 1, 5)] == 1.8


def test_score_counts_hits_and_misses(tmp_path):
    scored = newsletter.score(newsletter.load(_write(tmp_path)))
    by_day = {s.day: s for s in scored}
    assert by_day[date(2026, 1, 5)].correct and by_day[date(2026, 1, 5)].actual_ct == 4.0
    assert not by_day[date(2026, 1, 8)].correct


def test_backfill_keeps_existing_values(tmp_path):
    conn = history.connect(tmp_path / "p.sqlite")
    history.upsert(conn, history.DailyPrices(day=date(2026, 1, 7), diesel_max=2.5))
    written = newsletter.backfill(conn, newsletter.load(_write(tmp_path)))
    assert written == 5
    assert history.get(conn, date(2026, 1, 7)).diesel_max == 2.5
    assert history.get(conn, date(2026, 1, 7)).e10_max == 1.75
    assert history.get(conn, date(2026, 1, 6)).diesel_max == 2.0
