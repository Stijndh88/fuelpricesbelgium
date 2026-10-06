"""Refuel advice for diesel B7 and E10: fill up today, wait, or no difference.

The advice is deliberately simple and explains itself in one line. It uses, in order:

1. **Tomorrow's published maximum price.** FOD Economie publishes the next day's price in the
   afternoon of a working day. When it is known and differs from today's, the advice is certain.
2. **Brent crude since the last price change.** The real driver of a change is the wholesale
   product cost (Rotterdam quotations of finished diesel and petrol), which is not available for
   free. Brent is a rough stand-in: when it has moved far enough since the last change to leave
   the band of :mod:`fuelprices.rules`, a change in that direction is likely at the next
   computation.
3. Otherwise: no difference.

What it cannot know is listed in :data:`CAVEATS` and shipped with every JSON export.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from fuelprices import history, rules
from fuelprices.history import DailyPrices
from fuelprices.products import Product

FILL_UP = "fill_up_today"
WAIT = "wait"
NO_DIFFERENCE = "no_difference"
HEADLINES = {FILL_UP: "Fill up today", WAIT: "Wait", NO_DIFFERENCE: "No difference"}

# Changes smaller than this (EUR/L incl. VAT) are not worth changing your plans for.
MIN_CHANGE_EUR = 0.005

LITRES_PER_BARREL = 158.987
# Fixed EUR/USD rate for converting Brent; the real rate is not stored yet.
EUR_USD = 1.10
# Refining and transport on top of crude, EUR/L, so the band is a share of a realistic product
# cost rather than of crude alone. A rough average, not a quotation.
REFINING_EUR_PER_LITRE = 0.15
# Brent prices older than this are too stale to say anything about today.
MAX_BRENT_AGE_DAYS = 7

ADVISED_PRODUCTS = {Product.DIESEL_B7: "diesel_max", Product.E10: "e10_max"}

CAVEATS = [
    "The wholesale diesel and petrol quotations that actually trigger a change are not free, "
    "so beyond tomorrow's published price the advice uses Brent crude as a rough stand-in.",
    "The band widths of the price rules are placeholders until calibrated on the history.",
    "Brent is converted at a fixed EUR/USD rate and lags a few working days.",
    "Belgian public holidays and government price freezes are not taken into account.",
    "Pump prices can be below the official maximum; the advice is about the maximum price.",
]


@dataclass(frozen=True)
class Advice:
    product: str
    label: str
    action: str
    headline: str
    reason: str
    expected_change_cents: float | None
    basis: str  # "published", "brent" or "none"
    price_today: float | None
    price_tomorrow: float | None
    next_possible_change: str


def brent_to_eur_per_litre(brent_usd: float, eur_usd: float = EUR_USD) -> float:
    """Crude cost per litre in EUR, before refining, duties and VAT."""
    return brent_usd / eur_usd / LITRES_PER_BARREL


def next_possible_change(today: date) -> date:
    """First day a new maximum price can apply if it is not published yet for tomorrow."""
    day = today
    while not rules.is_computation_day(day):
        day += timedelta(days=1)
    return rules.effective_date(day)


def _price(rows: dict[date, DailyPrices], day: date, column: str) -> float | None:
    row = rows.get(day)
    return getattr(row, column) if row else None


def _last_change(rows: dict[date, DailyPrices], today: date, column: str) -> date | None:
    """The most recent day up to ``today`` on which the max price differed from the day before."""
    known = sorted(d for d, r in rows.items() if d <= today and getattr(r, column) is not None)
    for newer, older in zip(reversed(known[1:]), reversed(known[:-1]), strict=True):
        if getattr(rows[newer], column) != getattr(rows[older], column):
            return newer
    return None


def _brent_on_or_before(rows: dict[date, DailyPrices], day: date) -> tuple[date, float] | None:
    candidates = [d for d, r in rows.items() if d <= day and r.brent_usd is not None]
    if not candidates:
        return None
    found = max(candidates)
    return found, rows[found].brent_usd


def _working_days_between(start: date, end: date) -> int:
    return sum(
        rules.is_computation_day(start + timedelta(days=i)) for i in range((end - start).days)
    )


def _make(product, action, reason, change, basis, today_price, tomorrow_price, next_change):
    return Advice(
        product=product.code,
        label=product.label,
        action=action,
        headline=HEADLINES[action],
        reason=reason,
        expected_change_cents=None if change is None else round(change * 100, 1),
        basis=basis,
        price_today=today_price,
        price_tomorrow=tomorrow_price,
        next_possible_change=next_change.isoformat(),
    )


def advise(
    product: Product,
    rows: Sequence[DailyPrices],
    today: date,
    schedule: rules.ThresholdSchedule = rules.UNCONFIRMED_SCHEDULE,
) -> Advice:
    """Advise whether to refuel ``product`` today, using only ``rows`` (the stored history).

    Rows dated after tomorrow are ignored, so the same function replays history in the backtest.
    """
    column = ADVISED_PRODUCTS[product]
    by_day = {r.day: r for r in rows if r.day <= today + timedelta(days=1)}
    tomorrow = today + timedelta(days=1)
    price_today = _price(by_day, today, column)
    price_tomorrow = _price(by_day, tomorrow, column)
    next_change = next_possible_change(today)

    def make(action, reason, change, basis):
        return _make(
            product, action, reason, change, basis, price_today, price_tomorrow, next_change
        )

    if price_today is None:
        return make(NO_DIFFERENCE, "No maximum price known for today.", None, "none")

    if price_tomorrow is not None:
        change = price_tomorrow - price_today
        cents = f"{abs(change) * 100:.1f} cent/L"
        if change <= -MIN_CHANGE_EUR:
            return make(
                WAIT, f"The maximum price drops {cents} tomorrow (published).", change, "published"
            )
        if change >= MIN_CHANGE_EUR:
            return make(
                FILL_UP,
                f"The maximum price rises {cents} tomorrow (published).",
                change,
                "published",
            )
        if change != 0:
            return make(
                NO_DIFFERENCE,
                f"Tomorrow's price differs by only {cents} (published).",
                change,
                "published",
            )
        # Same price tomorrow: the next possible change is the computation after that.
        next_change = next_possible_change(tomorrow)

    return _brent_advice(product, by_day, today, column, schedule, make, next_change)


def _brent_advice(product, by_day, today, column, schedule, make, next_change):
    latest = _brent_on_or_before(by_day, today)
    if latest is None or (today - latest[0]).days > MAX_BRENT_AGE_DAYS:
        return make(
            NO_DIFFERENCE,
            "No recent Brent price and no published change for tomorrow.",
            None,
            "none",
        )

    # Without a change in the stored history, compare against the oldest known price instead.
    changed_on = _last_change(by_day, today, column) or min(
        d for d, r in by_day.items() if getattr(r, column) is not None
    )
    base = _brent_on_or_before(by_day, changed_on - timedelta(days=1)) or _brent_on_or_before(
        by_day, changed_on
    )
    if base is None:
        return make(
            NO_DIFFERENCE, "No Brent price from around the last price change.", None, "none"
        )

    base_cost = brent_to_eur_per_litre(base[1]) + REFINING_EUR_PER_LITRE
    move = brent_to_eur_per_litre(latest[1]) - brent_to_eur_per_litre(base[1])
    # The rules band applies to the product cost excluding VAT; the pump price moves with VAT.
    expected = move * (1 + rules.VAT_RATE)
    days_since = _working_days_between(changed_on, next_change)
    band = schedule.at(days_since) * base_cost
    brent_text = f"Brent {base[1]:.0f} to {latest[1]:.0f} USD since {changed_on:%d/%m}"
    when = f"{next_change:%a %d/%m}"

    if abs(move) < band or abs(expected) < MIN_CHANGE_EUR:
        return make(
            NO_DIFFERENCE,
            f"{brent_text}: inside the band, no change expected by {when}.",
            0.0,
            "brent",
        )
    if move < 0:
        return make(WAIT, f"{brent_text}: a drop is likely from {when}.", expected, "brent")
    return make(FILL_UP, f"{brent_text}: a rise is likely from {when}.", expected, "brent")


def advise_all(conn: sqlite3.Connection, today: date) -> list[Advice]:
    rows = history.all_rows(conn)
    return [advise(product, rows, today) for product in ADVISED_PRODUCTS]


@dataclass(frozen=True)
class BacktestResult:
    product: str
    windows: int
    saved: int
    same: int
    lost: int
    avg_saving_cents: float | None
    note: str


def backtest(
    product: Product, rows: Sequence[DailyPrices], horizon_days: int = 7
) -> BacktestResult:
    """Compare following the advice with filling up on a random day.

    For every start day with a known price for the whole window, you need fuel within
    ``horizon_days``. Following the advice means filling on the first day it does not say
    "wait" (or on the last day of the window). The random baseline pays the average price of the
    window. A saving counts when the advice paid at least 0.1 cent/L less.
    """
    column = ADVISED_PRODUCTS[product]
    prices = {r.day: getattr(r, column) for r in rows if getattr(r, column) is not None}
    savings = []
    for start in sorted(prices):
        window = [start + timedelta(days=i) for i in range(horizon_days)]
        if any(day not in prices for day in window):
            continue
        fill_day = window[-1]
        for day in window[:-1]:
            if advise(product, rows, day).action != WAIT:
                fill_day = day
                break
        baseline = sum(prices[day] for day in window) / len(window)
        savings.append(baseline - prices[fill_day])

    if not savings:
        return BacktestResult(
            product.code,
            0,
            0,
            0,
            0,
            None,
            f"Not enough history yet: needs {horizon_days} consecutive days with a price.",
        )
    saved = sum(s >= 0.001 for s in savings)
    lost = sum(s <= -0.001 for s in savings)
    avg = round(sum(savings) / len(savings) * 100, 2)
    return BacktestResult(
        product.code,
        len(savings),
        saved,
        len(savings) - saved - lost,
        lost,
        avg,
        f"Need to refuel within {horizon_days} days; following the advice versus a random day.",
    )


def export(conn: sqlite3.Connection, today: date) -> dict:
    rows = history.all_rows(conn)
    return {
        "as_of": today.isoformat(),
        "advice": [asdict(advise(p, rows, today)) for p in ADVISED_PRODUCTS],
        "caveats": CAVEATS,
        "backtest": [asdict(backtest(p, rows)) for p in ADVISED_PRODUCTS],
    }


def write_json(path: str | Path, data: dict) -> bool:
    """Write ``data`` as JSON; leaves the file untouched (and returns False) if nothing changed."""
    path = Path(path)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True
