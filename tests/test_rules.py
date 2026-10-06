from datetime import date, timedelta

import pytest

from fuelprices import rules
from fuelprices.products import Product

FLAT = rules.ThresholdSchedule((0.02,))


def test_max_price_adds_vat():
    structure = rules.PriceStructure(0.80, 0.20, 0.01, 0.60)
    assert structure.max_price() == round(1.61 * 1.21, 4)


def test_schedule_narrows_then_holds():
    schedule = rules.UNCONFIRMED_SCHEDULE
    assert schedule.at(1) > schedule.at(7)
    assert schedule.at(7) == schedule.at(30) == schedule.by_day[-1]


def test_threshold_needs_day_and_moving_average():
    # Today's cost jumps 5% but the 7-day average is still inside the band: no change.
    costs = [1.00] * 6 + [1.05]
    assert not rules.evaluate(Product.DIESEL_B7, costs, 1.00, 10, FLAT).changes

    # A sustained rise moves both above the band: price goes up, new base is today's cost.
    costs = [1.03] * 6 + [1.04]
    decision = rules.evaluate(Product.DIESEL_B7, costs, 1.00, 10, FLAT)
    assert decision.direction == 1
    assert decision.new_base_cost == 1.04


def test_threshold_down():
    # Mirrors the 5 Oct 2026 case: diesel cost fell from 1157 to 1095 EUR/1000 l and held.
    costs = [1.157] * 3 + [1.095] * 4
    assert rules.evaluate(Product.DIESEL_B7, costs, 1.157, 10, FLAT).direction == -1


def test_heating_oil_follows_daily_cost():
    decision = rules.evaluate(Product.HEATING_OIL, [1.00, 1.001], 1.00, 1, FLAT)
    assert decision.direction == 1
    assert decision.new_base_cost == 1.001


def test_empty_costs_rejected():
    with pytest.raises(ValueError):
        rules.evaluate(Product.E10, [], 1.0, 1)


def test_calendar_helpers():
    friday = date(2026, 10, 2)
    assert rules.is_computation_day(friday)
    assert not rules.is_computation_day(friday + timedelta(days=1))
    assert rules.effective_date(friday) == date(2026, 10, 3)
    assert rules.is_margin_indexation_day(date(2026, 10, 1))
    assert not rules.is_margin_indexation_day(date(2026, 10, 2))


def test_simulate_skips_weekends_and_rebases():
    start = date(2026, 9, 28)  # Monday
    days = [start + timedelta(days=i) for i in range(14)]
    costs = [1.00] * 5 + [9.99, 9.99] + [1.05] * 7  # weekend values must be ignored
    changes = rules.simulate(Product.DIESEL_B7, days, costs, 1.00, FLAT)

    assert len(changes) == 1
    change = changes[0]
    assert change.direction == 1
    assert change.computed_on.weekday() < 5
    assert change.effective_from == change.computed_on + timedelta(days=1)
    assert change.base_cost == 1.05
