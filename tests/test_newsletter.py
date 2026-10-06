from datetime import date

from fuelprices import history, newsletter

HEADER = (
    "date,diesel_now,e10_now,diesel_next,e10_next,next_effective,diesel_pred_dir,diesel_pred_ct,"
    "diesel_pred_day,e10_pred_dir,e10_pred_ct,e10_pred_day,diesel_product_eur_per_1000l,"
    "e10_product_eur_per_1000l,crude_usd\n"
)
ROWS = [
    # A diesel rise is forecast by Wednesday, E10 is announced down for Tuesday.
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


def _official():
    return {
        "diesel": {date(2026, 1, 5): 2.0, date(2026, 1, 7): 2.04, date(2026, 1, 9): 2.04},
        "e10": {date(2026, 1, 6): 1.75},
    }


def test_score_counts_hits_and_misses(tmp_path):
    scored = newsletter.score(newsletter.load(_write(tmp_path)), _official())
    by_day = {s.day: s for s in scored}
    assert by_day[date(2026, 1, 5)].correct and by_day[date(2026, 1, 5)].actual_ct == 4.0
    # Forecast "down" on 8 January, but no price known on the 8th, so it is skipped.
    assert date(2026, 1, 8) not in by_day


def test_score_marks_unchanged_price_as_miss(tmp_path):
    official = _official()
    official["diesel"][date(2026, 1, 8)] = 2.04
    scored = newsletter.score(newsletter.load(_write(tmp_path)), official)
    miss = [s for s in scored if s.day == date(2026, 1, 8)]
    assert len(miss) == 1 and not miss[0].correct and miss[0].actual_ct == 0.0


def test_check_reports_prices_that_differ_from_history(tmp_path):
    official = _official()
    official["diesel"][date(2026, 1, 5)] = 2.01
    found = newsletter.check(newsletter.load(_write(tmp_path)), official)
    assert found == [(date(2026, 1, 5), "diesel", date(2026, 1, 5), 2.0, 2.01)]


def test_official_series_skips_empty_days(tmp_path):
    conn = history.connect(tmp_path / "p.sqlite")
    history.upsert(conn, history.DailyPrices(day=date(2026, 1, 7), diesel_max=2.5))
    history.upsert(conn, history.DailyPrices(day=date(2026, 1, 8), e10_max=1.9))
    assert newsletter.official_series(conn, "diesel") == {date(2026, 1, 7): 2.5}
