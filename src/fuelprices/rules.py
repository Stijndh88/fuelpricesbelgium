"""The rules that decide when, and by how much, Belgian maximum fuel prices change.

The maximum prices are set under the programme contract between the Belgian State and the
petroleum sector (programma-overeenkomst of 9 October 2006, technical annex art. 13). See
``docs/price-rules.md`` for the sources and for which parts are confirmed.

In short:

* The maximum price is the sum of the product cost (from international quotations of the
  finished product, converted from USD per tonne at the EUR/USD rate), the distribution
  margin, contributions (APETRA/"Aseva", and for heating oil Promaz and the social heating
  fund) and excise duties, with 21% VAT on top.
* FOD Economie recomputes the product cost every working day. A new maximum price applies
  from the next day.
* Petrol, road diesel and LPG only change when *both* the day's product cost and its 7-day
  moving average leave a band around the product cost the current price was based on. The
  band narrows in the 7 days after a change.
* Heating oil (and red diesel) has no band since mid-2018: it follows the product cost daily.
* The distribution margin is indexed on 1 April and 1 October.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from fuelprices.products import ChangeRule, Product

VAT_RATE = 0.21
MOVING_AVERAGE_DAYS = 7
MARGIN_INDEXATION_DAYS = ((4, 1), (10, 1))


@dataclass(frozen=True)
class PriceStructure:
    """The parts of a maximum price, all in EUR per litre excluding VAT."""

    product_cost: float
    distribution_margin: float
    contributions: float
    excise: float

    def max_price(self, vat_rate: float = VAT_RATE) -> float:
        net = self.product_cost + self.distribution_margin + self.contributions + self.excise
        return round(net * (1 + vat_rate), 4)


@dataclass(frozen=True)
class ThresholdSchedule:
    """Width of the band (as a fraction of the base product cost) by days since the last change.

    ``by_day[0]`` applies on the first working day after a change, ``by_day[-1]`` from then on.
    """

    by_day: tuple[float, ...]

    def at(self, days_since_change: int) -> float:
        index = min(max(days_since_change - 1, 0), len(self.by_day) - 1)
        return self.by_day[index]


# The official percentages are in the technical annex, which is not published online. These
# values only reproduce the confirmed shape (a band that narrows over 7 days) and must be
# calibrated against the price history before predictions rely on them.
UNCONFIRMED_SCHEDULE = ThresholdSchedule((0.030, 0.0275, 0.025, 0.0225, 0.020, 0.0175, 0.015))


@dataclass(frozen=True)
class Decision:
    """Outcome of one day's evaluation. ``direction`` is +1 (up), -1 (down) or 0."""

    direction: int
    new_base_cost: float
    reason: str

    @property
    def changes(self) -> bool:
        return self.direction != 0


def evaluate(
    product: Product,
    product_costs: Sequence[float],
    base_cost: float,
    days_since_change: int,
    schedule: ThresholdSchedule = UNCONFIRMED_SCHEDULE,
) -> Decision:
    """Decide whether the maximum price of ``product`` changes after today's computation.

    ``product_costs`` are the daily product costs up to and including today, oldest first.
    ``base_cost`` is the product cost the current maximum price was computed from.
    """
    if not product_costs:
        raise ValueError("need at least today's product cost")
    today = product_costs[-1]

    if product.change_rule is ChangeRule.DAILY:
        direction = (today > base_cost) - (today < base_cost)
        return Decision(direction, today if direction else base_cost, "follows the daily cost")

    threshold = schedule.at(days_since_change)
    window = product_costs[-MOVING_AVERAGE_DAYS:]
    moving_average = sum(window) / len(window)
    day_deviation = (today - base_cost) / base_cost
    average_deviation = (moving_average - base_cost) / base_cost
    detail = (
        f"day {day_deviation:+.2%}, {len(window)}-day average {average_deviation:+.2%}, "
        f"band ±{threshold:.2%}"
    )

    if day_deviation > threshold and average_deviation > threshold:
        return Decision(+1, today, f"up: {detail}")
    if day_deviation < -threshold and average_deviation < -threshold:
        return Decision(-1, today, f"down: {detail}")
    return Decision(0, base_cost, f"no change: {detail}")


def is_computation_day(day: date) -> bool:
    """FOD Economie computes prices on working days. Belgian public holidays are not handled yet."""
    return day.weekday() < 5


def effective_date(computed_on: date) -> date:
    """A price computed on a working day applies from the next calendar day."""
    return computed_on + timedelta(days=1)


def is_margin_indexation_day(day: date) -> bool:
    return (day.month, day.day) in MARGIN_INDEXATION_DAYS


@dataclass(frozen=True)
class Change:
    computed_on: date
    effective_from: date
    direction: int
    base_cost: float
    reason: str


def simulate(
    product: Product,
    days: Sequence[date],
    product_costs: Sequence[float],
    initial_base_cost: float,
    schedule: ThresholdSchedule = UNCONFIRMED_SCHEDULE,
) -> list[Change]:
    """Replay the rules over a series of daily product costs and return the changes they cause.

    ``days`` and ``product_costs`` are aligned; non-working days are skipped. The first day is
    treated as if the last change happened long ago.
    """
    if len(days) != len(product_costs):
        raise ValueError("days and product_costs must have the same length")

    changes: list[Change] = []
    base = initial_base_cost
    days_since_change = len(schedule.by_day)
    seen: list[float] = []
    for day, cost in zip(days, product_costs, strict=True):
        if not is_computation_day(day):
            continue
        seen.append(cost)
        decision = evaluate(product, seen, base, days_since_change, schedule)
        if decision.changes:
            changes.append(
                Change(
                    day,
                    effective_date(day),
                    decision.direction,
                    decision.new_base_cost,
                    decision.reason,
                )
            )
            base = decision.new_base_cost
            days_since_change = 1
        else:
            days_since_change += 1
    return changes
