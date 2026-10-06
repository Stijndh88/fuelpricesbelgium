"""Fit the band widths of :mod:`fuelprices.rules` to the max-price changes that really happened.

The product cost that FOD Economie uses (Rotterdam quotations) is not free, so the fit runs on a
stand-in: the New York ULSD (diesel) or RBOB (petrol) future converted to EUR/L. The replayed
rules are scored on how well they reproduce the dates and directions of the real changes, on the
years used to fit and on a held-out last stretch. The advice only claims to predict a change when
the held-out score clears :data:`TRUST_MIN_PRECISION` and :data:`TRUST_MIN_RECALL`.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from fuelprices import rules
from fuelprices.history import DailyPrices
from fuelprices.products import Product

LITRES_PER_GALLON = 3.78541

# history columns per product: (max price, stand-in product cost in USD per gallon)
SERIES_COLUMNS = {
    Product.DIESEL_B7: ("diesel_max", "ulsd_usd_gal"),
    Product.E10: ("e10_max", "rbob_usd_gal"),
}

# A predicted change counts as the real one when it applies within this many days of it.
MATCH_WINDOW_DAYS = 1
# Replay changes before this many days from the start of the series are not scored: the replay
# starts without knowing the cost the first price was based on.
WARMUP_DAYS = 90
HOLDOUT_DAYS = 180
MIN_STEP_EUR = 0.002  # a smaller day-to-day move of the max price is not a change
# The advice only predicts changes when the held-out score is at least this good.
TRUST_MIN_PRECISION = 0.7
TRUST_MIN_RECALL = 0.7
TRUST_MIN_CHANGES = 8
SCHEDULE_DAYS = 7
DEFAULT_PATH = Path("data/calibration.json")


@dataclass(frozen=True)
class Series:
    """Aligned daily series: the stand-in product cost (EUR/L) and the real max price."""

    days: tuple[date, ...]  # days with a product cost
    costs: tuple[float, ...]
    prices: dict[date, float]  # real max price for every calendar day known


@dataclass(frozen=True)
class RealChange:
    effective_from: date
    direction: int  # +1 up, -1 down
    step: float  # change of the max price in EUR/L


@dataclass(frozen=True)
class Params:
    start: float  # band width on the first day after a change, as a fraction of the base cost
    end: float  # band width from the seventh day on
    lag: int  # the cost used on a computation day is from this many trading days earlier
    recenter: str  # "day" or "average": what the base cost becomes after a change

    def schedule(self) -> rules.ThresholdSchedule:
        step = (self.end - self.start) / (SCHEDULE_DAYS - 1)
        return rules.ThresholdSchedule(
            tuple(round(self.start + step * i, 6) for i in range(SCHEDULE_DAYS))
        )


@dataclass(frozen=True)
class Score:
    hits: int  # real changes the replay also produced (same direction, within the window)
    misses: int  # real changes the replay did not produce
    false_alarms: int  # replayed changes that did not happen
    same_day: int = 0  # hits on exactly the real day

    @property
    def precision(self) -> float:
        total = self.hits + self.false_alarms
        return self.hits / total if total else 0.0

    @property
    def recall(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def real_changes(self) -> int:
        return self.hits + self.misses


def build_series(rows: Iterable[DailyPrices], product: Product) -> Series:
    """The stand-in cost and real max price series of ``product`` from the stored history."""
    price_col, proxy_col = SERIES_COLUMNS[product]
    days, costs, prices = [], [], {}
    for row in sorted(rows, key=lambda r: r.day):
        price = getattr(row, price_col)
        if price is not None:
            prices[row.day] = price
        proxy = getattr(row, proxy_col)
        if proxy is not None and row.eur_usd:
            days.append(row.day)
            costs.append(proxy / LITRES_PER_GALLON / row.eur_usd)
    return Series(tuple(days), tuple(costs), prices)


def real_changes(prices: dict[date, float]) -> list[RealChange]:
    """Every day the max price differs from the day before, apart from margin indexation days."""
    changes = []
    ordered = sorted(prices)
    for before, day in zip(ordered, ordered[1:], strict=False):
        if (day - before).days != 1 or rules.is_margin_indexation_day(day):
            continue
        step = prices[day] - prices[before]
        if abs(step) >= MIN_STEP_EUR:
            changes.append(RealChange(day, 1 if step > 0 else -1, step))
    return changes


def replay(product: Product, series: Series, params: Params) -> list[rules.Change]:
    """Run the rules over the stand-in cost series with ``params``."""
    if not series.days:
        return []
    costs = list(series.costs)
    if params.lag:
        costs = [costs[0]] * params.lag + costs[: -params.lag]
    return rules.simulate(
        product,
        list(series.days),
        costs,
        costs[0],
        params.schedule(),
        params.recenter,
    )


def score_changes(
    replayed: Sequence[rules.Change],
    actual: Sequence[RealChange],
    start: date,
    end: date,
    window: int = MATCH_WINDOW_DAYS,
) -> Score:
    """Compare replayed and real changes that apply from ``start`` up to and including ``end``."""
    unmatched = [a for a in actual if start <= a.effective_from <= end]
    hits = same_day = false_alarms = 0
    for change in replayed:
        if not start <= change.effective_from <= end:
            continue
        if rules.is_margin_indexation_day(change.effective_from):
            continue
        match = next(
            (
                a
                for a in unmatched
                if a.direction == change.direction
                and abs((a.effective_from - change.effective_from).days) <= window
            ),
            None,
        )
        if match:
            unmatched.remove(match)
            hits += 1
            same_day += match.effective_from == change.effective_from
        else:
            false_alarms += 1
    return Score(hits, len(unmatched), false_alarms, same_day)


def grid() -> list[Params]:
    starts = [x / 1000 for x in range(10, 61, 5)]
    ends = [x / 1000 for x in range(5, 41, 5)]
    return [
        Params(start, end, lag, recenter)
        for start in starts
        for end in ends
        if end <= start
        for lag in (0, 1)
        for recenter in ("day", "average")
    ]


@dataclass(frozen=True)
class Calibration:
    """The outcome of a fit for one product, as stored in ``data/calibration.json``."""

    product: str
    params: Params | None
    train_from: str | None
    train_to: str | None
    test_from: str | None
    test_to: str | None
    train: Score | None
    test: Score | None
    pass_through: float | None  # real max price change per EUR of stand-in cost change, incl. VAT
    trusted: bool
    note: str


def is_trusted(test: Score | None) -> bool:
    return (
        test is not None
        and test.real_changes >= TRUST_MIN_CHANGES
        and test.precision >= TRUST_MIN_PRECISION
        and test.recall >= TRUST_MIN_RECALL
    )


def pass_through(
    replayed: Sequence[rules.Change], actual: Sequence[RealChange], series: Series
) -> float | None:
    """Median ratio of the real price step to the stand-in cost move behind each matched change."""
    cost_on = dict(zip(series.days, series.costs, strict=True))
    ratios = []
    base = series.costs[0] if series.costs else None
    for change in replayed:
        real = next(
            (
                a
                for a in actual
                if a.direction == change.direction
                and abs((a.effective_from - change.effective_from).days) <= MATCH_WINDOW_DAYS
            ),
            None,
        )
        new_cost = cost_on.get(change.computed_on)
        if real and base and new_cost and new_cost != base:
            ratios.append(real.step / ((new_cost - base) * (1 + rules.VAT_RATE)))
        base = change.base_cost
    return round(statistics.median(ratios), 3) if ratios else None


def calibrate_product(
    product: Product,
    rows: Iterable[DailyPrices],
    holdout_days: int = HOLDOUT_DAYS,
) -> Calibration:
    """Fit the band to everything before the held-out last ``holdout_days`` and score both parts."""
    series = build_series(rows, product)
    actual = real_changes(series.prices)
    name = product.code
    if len(series.days) < WARMUP_DAYS + 2 * holdout_days or not actual:
        return Calibration(
            name, None, None, None, None, None, None, None, None, False,
            "Not enough history with product costs and max prices to fit the rules.",
        )  # fmt: skip
    first = series.days[0] + timedelta(days=WARMUP_DAYS)
    last = max(series.prices)
    split = last - timedelta(days=holdout_days)

    best: tuple[Params, Score] | None = None
    for params in grid():
        replayed = replay(product, series, params)
        train = score_changes(replayed, actual, first, split)
        if best is None or train.f1 > best[1].f1:
            best = (params, train)
    assert best is not None
    params, train = best
    replayed = replay(product, series, params)
    test = score_changes(replayed, actual, split + timedelta(days=1), last)
    trusted = is_trusted(test)
    note = (
        "Held-out score is good enough to predict changes."
        if trusted
        else "Held-out score is too low to trust: predictions stay labelled as a guess."
    )
    return Calibration(
        name,
        params,
        first.isoformat(),
        split.isoformat(),
        (split + timedelta(days=1)).isoformat(),
        last.isoformat(),
        train,
        test,
        pass_through(replayed, actual, series),
        trusted,
        note,
    )


@dataclass(frozen=True)
class StandInCheck:
    """How closely the stand-in cost follows the product prices quoted in the newsletter."""

    product: str
    points: int
    correlation: float | None
    mean_gap: float | None  # newsletter minus stand-in, EUR per 1000 L
    gap_sd: float | None


NEWSLETTER_COLUMNS = {
    Product.DIESEL_B7: "diesel_product_eur_per_1000l",
    Product.E10: "e10_product_eur_per_1000l",
}


def stand_in_check(rows: Sequence[DailyPrices], newsletter: Path) -> dict[str, StandInCheck]:
    """Compare the stand-in product cost with the Rotterdam prices quoted in the newsletter.

    The newsletter gives a wholesale price (EUR per 1000 L) in only some issues, so this is a
    check of the stand-in, not a series to fit on.
    """
    with newsletter.open(encoding="utf-8", newline="") as handle:
        issues = list(csv.DictReader(handle))
    result = {}
    for product, column in NEWSLETTER_COLUMNS.items():
        series = build_series(rows, product)
        cost_on = dict(zip(series.days, series.costs, strict=True))
        quoted, proxy = [], []
        for issue in issues:
            if not issue.get(column):
                continue
            day = date.fromisoformat(issue["date"])
            known = [d for d in cost_on if d <= day]
            if known:
                quoted.append(float(issue[column]))
                proxy.append(cost_on[max(known)] * 1000)
        gaps = [q - p for q, p in zip(quoted, proxy, strict=True)]
        corr = None
        if len(quoted) >= 3 and statistics.pstdev(quoted) and statistics.pstdev(proxy):
            corr = round(statistics.correlation(quoted, proxy), 2)
        result[product.code] = StandInCheck(
            product.code,
            len(quoted),
            corr,
            round(statistics.mean(gaps)) if gaps else None,
            round(statistics.pstdev(gaps)) if gaps else None,
        )
    return result


def calibrate_all(rows: Sequence[DailyPrices]) -> dict[str, Calibration]:
    return {p.code: calibrate_product(p, rows) for p in SERIES_COLUMNS}


def report_stand_in(checks: dict[str, StandInCheck]) -> str:
    lines = ["Stand-in cost against the product prices quoted in the newsletter:"]
    for c in checks.values():
        if c.points < 3:
            lines.append(f"  {c.product}: only {c.points} quoted prices, too few to compare")
            continue
        lines.append(
            f"  {c.product}: {c.points} quotes, correlation {c.correlation}, newsletter minus "
            f"stand-in {c.mean_gap:+} EUR/1000 L on average (spread {c.gap_sd})"
        )
    return "\n".join(lines)


def to_json(calibrations: dict[str, Calibration]) -> str:
    return json.dumps({k: asdict(v) for k, v in calibrations.items()}, indent=2) + "\n"


def from_json(text: str) -> dict[str, Calibration]:
    result = {}
    for name, c in json.loads(text).items():
        params = Params(**c["params"]) if c.get("params") else None
        train = Score(**c["train"]) if c.get("train") else None
        test = Score(**c["test"]) if c.get("test") else None
        result[name] = Calibration(
            **{**c, "params": params, "train": train, "test": test},
        )
    return result


def save(path: Path, calibrations: dict[str, Calibration]) -> bool:
    text = to_json(calibrations)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def load(path: Path = DEFAULT_PATH) -> dict[str, Calibration]:
    try:
        return from_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def report(calibrations: dict[str, Calibration]) -> str:
    lines = []
    for c in calibrations.values():
        lines.append(f"{c.product}: {c.note}")
        if c.params is None:
            continue
        p = c.params
        lines.append(
            f"  band {p.start:.1%} narrowing to {p.end:.1%} over {SCHEDULE_DAYS} days, "
            f"cost lag {p.lag}, new base = {p.recenter}"
        )
        for label, s, a, b in (
            ("fit ", c.train, c.train_from, c.train_to),
            ("held-out", c.test, c.test_from, c.test_to),
        ):
            if s:
                lines.append(
                    f"  {label} {a}..{b}: {s.real_changes} real changes, hits {s.hits} "
                    f"({s.same_day} on the exact day), misses {s.misses}, false alarms "
                    f"{s.false_alarms}; precision {s.precision:.0%}, recall {s.recall:.0%}"
                )
        if c.pass_through is not None:
            lines.append(f"  real price step per stand-in cost move (incl. VAT): {c.pass_through}")
    return "\n".join(lines)
