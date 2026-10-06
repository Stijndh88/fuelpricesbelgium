import json
import random
from datetime import date, timedelta

from fuelprices import calibrate, rules
from fuelprices.history import DailyPrices
from fuelprices.products import Product

START = date(2023, 1, 2)
TRUE = calibrate.Params(0.03, 0.015, 0, "day")


def synthetic_rows(days=900, seed=7, params=TRUE, noise=0.0):
    """A random-walk cost series and the max prices the rules produce from it."""
    rng = random.Random(seed)
    cost, costs, day_list = 0.80, [], []
    for i in range(days):
        cost *= 1 + rng.gauss(0, 0.012)
        costs.append(cost)
        day_list.append(START + timedelta(days=i))
    changes = rules.simulate(
        Product.DIESEL_B7, day_list, costs, costs[0], params.schedule(), params.recenter
    )
    by_effective = {c.effective_from: c for c in changes}
    cost_by_day = dict(zip(day_list, costs, strict=True))
    # Each change moves the price with the cost it was computed from.
    price = 1.60
    base = costs[0]
    out = []
    for day, c in zip(day_list, costs, strict=True):
        change = by_effective.get(day)
        if change:
            new_cost = cost_by_day[change.computed_on]
            price += (new_cost - base) * (1 + rules.VAT_RATE)
            base = new_cost
        proxy = c * calibrate.LITRES_PER_GALLON * (1 + noise * rng.gauss(0, 1))
        out.append(
            DailyPrices(day=day, diesel_max=round(price, 4), ulsd_usd_gal=proxy, eur_usd=1.0)
        )
    return out


def test_real_changes_skip_margin_indexation_days():
    prices = {
        date(2026, 9, 30): 2.40,
        date(2026, 10, 1): 2.412,  # +1 cent margin indexation
        date(2026, 10, 2): 2.392,
        date(2026, 10, 3): 2.392,
    }
    changes = calibrate.real_changes(prices)
    assert [(c.effective_from, c.direction) for c in changes] == [(date(2026, 10, 2), -1)]


def test_score_counts_hits_misses_and_false_alarms():
    actual = [
        calibrate.RealChange(date(2026, 3, 3), -1, -0.03),
        calibrate.RealChange(date(2026, 3, 10), +1, 0.02),
    ]
    replayed = [
        rules.Change(date(2026, 3, 1), date(2026, 3, 2), -1, 1.0, ""),  # a day early: still a hit
        rules.Change(date(2026, 3, 20), date(2026, 3, 21), -1, 1.0, ""),  # never happened
    ]
    score = calibrate.score_changes(replayed, actual, date(2026, 1, 1), date(2026, 12, 31))
    assert (score.hits, score.misses, score.false_alarms, score.same_day) == (1, 1, 1, 0)
    assert score.precision == 0.5 and score.recall == 0.5


def test_a_known_band_is_recovered_and_trusted():
    cal = calibrate.calibrate_product(Product.DIESEL_B7, synthetic_rows())
    assert cal.params is not None
    assert cal.test.real_changes >= calibrate.TRUST_MIN_CHANGES
    assert cal.test.precision >= 0.9 and cal.test.recall >= 0.9
    assert cal.trusted
    # The pass-through of the cost move into the max price (with VAT) is 1 by construction.
    assert abs(cal.pass_through - 1.0) < 0.05


def test_pure_noise_is_not_trusted():
    rng = random.Random(3)
    rows = synthetic_rows()
    shuffled = [
        DailyPrices(
            day=r.day,
            diesel_max=round(1.6 + (0.05 if rng.random() < 0.1 else 0) * rng.choice((-1, 1)), 4),
            ulsd_usd_gal=r.ulsd_usd_gal,
            eur_usd=1.0,
        )
        for r in rows
    ]
    assert not calibrate.calibrate_product(Product.DIESEL_B7, shuffled).trusted


def test_too_little_history_is_not_trusted():
    cal = calibrate.calibrate_product(Product.DIESEL_B7, synthetic_rows(days=100))
    assert not cal.trusted and cal.params is None
    assert "Not enough history" in cal.note


def test_calibration_json_round_trip(tmp_path):
    result = calibrate.calibrate_all(synthetic_rows())
    path = tmp_path / "calibration.json"
    assert calibrate.save(path, result)
    assert not calibrate.save(path, result)
    assert calibrate.load(path) == result
    assert json.loads(path.read_text())["diesel_b7"]["trusted"] is True
    assert calibrate.load(tmp_path / "missing.json") == {}


def test_stand_in_check_compares_with_newsletter_quotes(tmp_path):
    start = date(2026, 6, 1)
    rows = [
        DailyPrices(day=start + timedelta(days=i), ulsd_usd_gal=3.0 + 0.1 * i, eur_usd=1.0)
        for i in range(10)
    ]
    cost = lambda i: (3.0 + 0.1 * i) / calibrate.LITRES_PER_GALLON * 1000  # noqa: E731
    path = tmp_path / "n.csv"
    lines = ["date,diesel_product_eur_per_1000l,e10_product_eur_per_1000l"]
    for i in (1, 4, 8):
        lines.append(f"{(start + timedelta(days=i)).isoformat()},{cost(i) + 30:.0f},")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    check = calibrate.stand_in_check(rows, path)
    assert check["diesel_b7"].points == 3
    assert check["diesel_b7"].correlation == 1.0
    assert check["diesel_b7"].mean_gap == 30
    assert check["e10"].points == 0
    assert "too few" in calibrate.report_stand_in(check)
