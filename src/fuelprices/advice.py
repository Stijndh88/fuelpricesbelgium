"""Refuel advice for diesel B7 and E10: fill up today, wait, or no difference.

The advice is deliberately simple and explains itself in one line. It uses, in order:

1. **Tomorrow's published maximum price.** FOD Economie publishes the next day's price in the
   afternoon of a working day. When it is known and differs from today's, the advice is certain.
2. **Brent crude since the last price change.** The real driver of a change is the wholesale
   product cost (Rotterdam quotations of finished diesel and petrol), which is not available for
   free. Brent is a rough stand-in: when it has moved far enough since the last change to leave
   the band of :mod:`fuelprices.rules`, a change in that direction is likely at the next
   computation.
3. **A market shock.** When Brent or the matching product future (US diesel or gasoline) moved
   more than :data:`SHOCK_THRESHOLD` over :data:`SHOCK_DAYS` days, the max price is likely to
   follow within days, whatever the band says. This runs before step 2.
4. Otherwise: no difference.

What it cannot know is listed in :data:`CAVEATS` and shipped with every JSON export.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from fuelprices import calibrate, history, messages, rules
from fuelprices.history import DailyPrices
from fuelprices.products import Product

FILL_UP = "fill_up_today"
WAIT = "wait"
NO_DIFFERENCE = "no_difference"

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

# A move of the market of at least this fraction over SHOCK_DAYS calendar days counts as a shock.
SHOCK_THRESHOLD = 0.05
SHOCK_DAYS = 5
BACKTEST_DAYS = 365  # the backtest looks at the most recent year only
LITRES_PER_GALLON = 3.78541
# Market series checked for shocks per product: (history column, name in the reason).
SHOCK_SERIES = {
    Product.DIESEL_B7: (("ulsd_usd_gal", "Diesel futures"), ("brent_usd", "Brent")),
    Product.E10: (("rbob_usd_gal", "Gasoline futures"), ("brent_usd", "Brent")),
}

CAVEAT_CODES = list(messages.CAVEATS)
CAVEATS = [messages.caveat(code) for code in CAVEAT_CODES]


@dataclass(frozen=True)
class Advice:
    product: str
    label: str
    action: str
    headline: str
    reason: str
    expected_change_cents: float | None
    basis: str  # "published", "rules", "shock", "brent" or "none"
    price_today: float | None
    price_tomorrow: float | None
    next_possible_change: str
    market_note: str | None = None  # a big market move, shown even when it does not decide
    reason_code: str | None = None  # message code, see fuelprices.messages
    reason_params: dict | None = None
    market_note_params: dict | None = None
    is_guess: bool = True  # False only for a published price or a rules fit that passed its test


@dataclass(frozen=True)
class MarketMove:
    name: str
    change: float  # fraction, +0.06 is a 6% rise
    eur_per_litre: float  # the same move in EUR/L incl. VAT, as a rough pump price effect
    since: date

    @property
    def params(self) -> dict:
        return {
            "name": self.name,
            "pct": round(self.change * 100, 1),
            "since": self.since.isoformat(),
        }


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


def _price_in_force(rows: dict[date, DailyPrices], day: date, column: str) -> float | None:
    """The max price valid on ``day``: it stays in force until a new one is published."""
    known = [d for d, r in rows.items() if d <= day and getattr(r, column) is not None]
    return getattr(rows[max(known)], column) if known else None


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


def _value_on_or_before(rows, column, day):
    candidates = [d for d, r in rows.items() if d <= day and getattr(r, column) is not None]
    if not candidates:
        return None
    found = max(candidates)
    return found, getattr(rows[found], column)


def _to_eur_per_litre(column: str, value: float) -> float:
    if column == "brent_usd":
        return brent_to_eur_per_litre(value)
    return value / EUR_USD / LITRES_PER_GALLON


def market_moves(
    product: Product, rows: dict[date, DailyPrices], today: date, days: int = SHOCK_DAYS
) -> list[MarketMove]:
    """How much each market series for ``product`` moved over the last ``days`` days."""
    moves = []
    for column, name in SHOCK_SERIES[product]:
        latest = _value_on_or_before(rows, column, today)
        if latest is None or (today - latest[0]).days > MAX_BRENT_AGE_DAYS:
            continue
        start = _value_on_or_before(rows, column, latest[0] - timedelta(days=days))
        if start is None or (latest[0] - start[0]).days > days + 3:
            continue
        eur = _to_eur_per_litre(column, latest[1]) - _to_eur_per_litre(column, start[1])
        moves.append(
            MarketMove(name, latest[1] / start[1] - 1, eur * (1 + rules.VAT_RATE), start[0])
        )
    return moves


def shock(moves: Sequence[MarketMove], threshold: float) -> MarketMove | None:
    """The largest move beyond ``threshold``, unless big moves disagree on the direction."""
    big = [m for m in moves if abs(m.change) >= threshold]
    if not big or len({m.change > 0 for m in big}) > 1:
        return None
    return max(big, key=lambda m: abs(m.change))


def _working_days_between(start: date, end: date) -> int:
    return sum(
        rules.is_computation_day(start + timedelta(days=i)) for i in range((end - start).days)
    )


def _make(
    product, action, code, params, change, basis, today_price, tomorrow_price, next_change, note
):
    return Advice(
        product=product.code,
        label=product.label,
        action=action,
        headline=messages.headline(action),
        reason=messages.reason(code, params),
        reason_code=code,
        reason_params=params,
        expected_change_cents=None if change is None else round(change * 100, 1),
        basis=basis,
        price_today=today_price,
        price_tomorrow=tomorrow_price,
        next_possible_change=next_change.isoformat(),
        market_note=messages.market_note(note) if note else None,
        market_note_params=note,
        is_guess=basis not in ("published", "rules", "none"),
    )


def advise(
    product: Product,
    rows: Sequence[DailyPrices],
    today: date,
    schedule: rules.ThresholdSchedule = rules.UNCONFIRMED_SCHEDULE,
    shock_threshold: float | None = SHOCK_THRESHOLD,
    calibration: calibrate.Calibration | None = None,
) -> Advice:
    """Advise whether to refuel ``product`` today, using only ``rows`` (the stored history).

    Rows dated after tomorrow are ignored, so the same function replays history in the backtest.
    ``shock_threshold=None`` turns the market shock flag off. A ``calibration`` whose fit passed
    its held-out test supplies the band widths and lets the rules band predict a change as
    "rules"; without one, or when it failed, that prediction stays labelled a guess.
    """
    trusted = calibration is not None and calibration.trusted and calibration.params is not None
    if trusted:
        schedule = calibration.params.schedule()
    column = ADVISED_PRODUCTS[product]
    by_day = {r.day: r for r in rows if r.day <= today + timedelta(days=1)}
    tomorrow = today + timedelta(days=1)
    price_today = _price_in_force(by_day, today, column)
    price_tomorrow = _price(by_day, tomorrow, column)
    next_change = next_possible_change(today)
    big_move = None
    if shock_threshold is not None:
        big_move = shock(market_moves(product, by_day, today), shock_threshold)
    note = big_move.params if big_move else None

    def make(action, code, params, change, basis, next_day=None):
        return _make(
            product,
            action,
            code,
            params,
            change,
            basis,
            price_today,
            price_tomorrow,
            next_day or next_change,
            note,
        )

    if price_today is None:
        if price_tomorrow is not None:
            return make(NO_DIFFERENCE, "tomorrow_only", {"tomorrow": price_tomorrow}, None, "none")
        return make(NO_DIFFERENCE, "no_price_today", {}, None, "none")

    if price_tomorrow is not None:
        change = price_tomorrow - price_today
        params = {
            "day": tomorrow.isoformat(),
            "cents": round(abs(change) * 100, 1),
            "today": price_today,
            "tomorrow": price_tomorrow,
        }
        if change <= -MIN_CHANGE_EUR:
            return make(WAIT, "wait_published", params, change, "published")
        if change >= MIN_CHANGE_EUR:
            return make(FILL_UP, "fill_published", params, change, "published")
        if change != 0:
            return make(
                NO_DIFFERENCE,
                "small_change",
                {"cents": round(abs(change) * 100, 1)},
                change,
                "published",
            )
        # Same price tomorrow: the next possible change is the computation after that.
        next_change = next_possible_change(tomorrow)

    if big_move and abs(big_move.eur_per_litre) >= MIN_CHANGE_EUR:
        params = {**big_move.params, "when": next_change.isoformat()}
        if big_move.change < 0:
            return make(WAIT, "shock_wait", params, big_move.eur_per_litre, "shock", next_change)
        return make(FILL_UP, "shock_fill", params, big_move.eur_per_litre, "shock", next_change)

    basis = "rules" if trusted else "brent"
    if product is Product.DIESEL_B7:
        found = _gasoil_advice(by_day, today, column, schedule, make, next_change, trusted)
        if found is not None:
            return found
    return _brent_advice(product, by_day, today, column, schedule, make, next_change, basis)


def _gasoil_advice(by_day, today, column, schedule, make_any, next_change, trusted):
    """Diesel guess from the official daily gasoil cost (the heating oil max price), if stored.

    The heating oil price valid on day D+1 is the cost of working day D, without a band, so the
    cost of today is known this morning. The diesel price in force was set from the cost of the
    day before its start (``heating[changed_on]``). Returns None when that history is missing.
    """
    changed_on = _last_change(by_day, today, column)
    known = [
        by_day[d]
        for d in (today + timedelta(days=1), today)
        if d in by_day and by_day[d].heating_oil_max is not None
    ]
    now = known[0] if known else None
    base = by_day.get(changed_on) if changed_on else None
    if now is None or base is None or not base.heating_oil_max:
        return None
    if (today - now.day).days > MAX_BRENT_AGE_DAYS:
        return None
    # Incl. VAT, so the difference is the move of the pump price itself.
    expected = now.heating_oil_max - base.heating_oil_max
    base_cost = base.heating_oil_max / (1 + rules.VAT_RATE)
    days_since = _working_days_between(changed_on, next_change)
    band = schedule.at(days_since) * base_cost
    params = {
        "cost_from": base.heating_oil_max,
        "cost_to": now.heating_oil_max,
        "since": changed_on.isoformat(),
        "when": next_change.isoformat(),
    }
    basis = "rules" if trusted else "gasoil"
    guess = "" if trusted else "_guess"
    if abs(expected) / (1 + rules.VAT_RATE) < band or abs(expected) < MIN_CHANGE_EUR:
        return make_any("no_difference", "gasoil_inside_band", params, 0.0, basis, next_change)
    code = "gasoil_wait" if expected < 0 else "gasoil_fill"
    action = WAIT if expected < 0 else FILL_UP
    return make_any(action, f"{code}{guess}", params, expected, basis, next_change)


def _brent_advice(product, by_day, today, column, schedule, make_any, next_change, basis="brent"):
    def make(action, code, params, change, basis):
        return make_any(action, code, params, change, basis, next_change)

    latest = _brent_on_or_before(by_day, today)
    if latest is None or (today - latest[0]).days > MAX_BRENT_AGE_DAYS:
        return make(NO_DIFFERENCE, "brent_no_data", {}, None, "none")

    # Without a change in the stored history, compare against the oldest known price instead.
    changed_on = _last_change(by_day, today, column) or min(
        d for d, r in by_day.items() if getattr(r, column) is not None
    )
    base = _brent_on_or_before(by_day, changed_on - timedelta(days=1)) or _brent_on_or_before(
        by_day, changed_on
    )
    if base is None:
        return make(NO_DIFFERENCE, "brent_no_base", {}, None, "none")

    base_cost = brent_to_eur_per_litre(base[1]) + REFINING_EUR_PER_LITRE
    move = brent_to_eur_per_litre(latest[1]) - brent_to_eur_per_litre(base[1])
    # The rules band applies to the product cost excluding VAT; the pump price moves with VAT.
    expected = move * (1 + rules.VAT_RATE)
    days_since = _working_days_between(changed_on, next_change)
    band = schedule.at(days_since) * base_cost
    params = {
        "brent_from": base[1],
        "brent_to": latest[1],
        "since": changed_on.isoformat(),
        "when": next_change.isoformat(),
    }

    if abs(move) < band or abs(expected) < MIN_CHANGE_EUR:
        return make(NO_DIFFERENCE, "brent_inside_band", params, 0.0, basis)
    guess = "" if basis == "rules" else "_guess"
    if move < 0:
        return make(WAIT, f"brent_wait{guess}", params, expected, basis)
    return make(FILL_UP, f"brent_fill{guess}", params, expected, basis)


def advise_all(
    conn: sqlite3.Connection,
    today: date,
    shock_threshold: float | None = SHOCK_THRESHOLD,
    calibrations: dict[str, calibrate.Calibration] | None = None,
) -> list[Advice]:
    rows = history.all_rows(conn)
    calibrations = calibrations or {}
    return [
        advise(
            product,
            rows,
            today,
            shock_threshold=shock_threshold,
            calibration=calibrations.get(product.code),
        )
        for product in ADVISED_PRODUCTS
    ]


@dataclass(frozen=True)
class BacktestResult:
    product: str
    shock_threshold: float | None  # None: shock flag off
    windows: int
    saved: int
    same: int
    lost: int
    avg_saving_cents: float | None
    note: str


def backtest(
    product: Product,
    rows: Sequence[DailyPrices],
    horizon_days: int = 7,
    shock_threshold: float | None = SHOCK_THRESHOLD,
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
    recent = max(prices, default=None)
    for start in sorted(prices):
        if recent and (recent - start).days > BACKTEST_DAYS:
            continue
        window = [start + timedelta(days=i) for i in range(horizon_days)]
        if any(day not in prices for day in window):
            continue
        fill_day = window[-1]
        for day in window[:-1]:
            if advise(product, rows, day, shock_threshold=shock_threshold).action != WAIT:
                fill_day = day
                break
        baseline = sum(prices[day] for day in window) / len(window)
        savings.append(baseline - prices[fill_day])

    if not savings:
        return BacktestResult(
            product.code,
            shock_threshold,
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
        shock_threshold,
        len(savings),
        saved,
        len(savings) - saved - lost,
        lost,
        avg,
        f"Need to refuel within {horizon_days} days; following the advice versus a random day.",
    )


def export(
    conn: sqlite3.Connection,
    today: date,
    shock_threshold: float | None = SHOCK_THRESHOLD,
    calibrations: dict[str, calibrate.Calibration] | None = None,
) -> dict:
    """Advice for today plus a backtest with and without the market shock flag."""
    rows = history.all_rows(conn)
    calibrations = calibrations or {}
    thresholds = [None] if shock_threshold is None else [None, shock_threshold]
    return {
        "as_of": today.isoformat(),
        "shock_threshold": shock_threshold,
        "advice": [
            asdict(
                advise(
                    p,
                    rows,
                    today,
                    shock_threshold=shock_threshold,
                    calibration=calibrations.get(p.code),
                )
            )
            for p in ADVISED_PRODUCTS
        ],
        "calibration": {code: _calibration_summary(c) for code, c in calibrations.items()},
        "caveats": CAVEATS,
        "caveat_codes": CAVEAT_CODES,
        "backtest": [
            asdict(backtest(p, rows, shock_threshold=t))
            for p in ADVISED_PRODUCTS
            for t in thresholds
        ],
    }


def _calibration_summary(c: calibrate.Calibration) -> dict:
    test = c.test
    return {
        "trusted": c.trusted,
        "note": c.note,
        "held_out_from": c.test_from,
        "held_out_to": c.test_to,
        "real_changes": test.real_changes if test else None,
        "precision": round(test.precision, 2) if test else None,
        "recall": round(test.recall, 2) if test else None,
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
