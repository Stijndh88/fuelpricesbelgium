"""Facts extracted from the Energieprijzen.vlaanderen newsletter.

The file is ``data/newsletter_predictions.csv``.

The newsletter states the official maximum price valid today, the one published for the next
change, and a forecast of the next price change. Only those numbers are stored, never newsletter
text. This module loads the file, turns the stated prices into a daily series of maximum prices
(used to backfill ``data/prices.sqlite``) and scores the forecasts against that series.

Run ``python -m fuelprices.newsletter score`` or ``... backfill``.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from fuelprices import history
from fuelprices.history import DailyPrices

DEFAULT_PATH = Path("data/newsletter_predictions.csv")
FUELS = ("diesel", "e10")


@dataclass(frozen=True)
class Forecast:
    direction: str  # up, down, flat, up_conditional, down_conditional
    size_ct: float | None  # euro cent per litre; midpoint when the newsletter gave a range
    last_day: date | None  # last day the change is expected on


@dataclass(frozen=True)
class Issue:
    day: date
    now: dict[str, float | None]
    next_price: dict[str, float | None]
    next_effective: date | None
    forecast: dict[str, Forecast | None]
    product_eur_per_1000l: dict[str, float | None]
    crude_usd: float | None


def _float(text: str) -> float | None:
    return float(text) if text else None


def _last_day(text: str) -> date | None:
    return date.fromisoformat(text.split("/")[-1]) if text else None


def _size(text: str) -> float | None:
    if not text:
        return None
    parts = [float(p) for p in text.split("-")]
    return sum(parts) / len(parts)


def load(path: Path = DEFAULT_PATH) -> list[Issue]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    issues = []
    for r in rows:
        forecast: dict[str, Forecast | None] = {}
        for fuel in FUELS:
            direction = r[f"{fuel}_pred_dir"]
            forecast[fuel] = (
                Forecast(direction, _size(r[f"{fuel}_pred_ct"]), _last_day(r[f"{fuel}_pred_day"]))
                if direction
                else None
            )
        issues.append(
            Issue(
                day=date.fromisoformat(r["date"]),
                now={f: _float(r[f"{f}_now"]) for f in FUELS},
                next_price={f: _float(r[f"{f}_next"]) for f in FUELS},
                next_effective=(
                    date.fromisoformat(r["next_effective"].split("/")[0])
                    if r["next_effective"]
                    else None
                ),
                forecast=forecast,
                product_eur_per_1000l={f: _float(r[f"{f}_product_eur_per_1000l"]) for f in FUELS},
                crude_usd=_float(r["crude_usd"]),
            )
        )
    return sorted(issues, key=lambda i: i.day)


def daily_max_prices(issues: list[Issue], fuel: str) -> dict[date, float]:
    """Maximum price per day for days the newsletters pin down.

    A price stated for a day (today's, or the next one from its effective day) is a fixed
    point. Between two fixed points the price is carried forward only when both agree; when
    they differ the change day is unknown, so the days in between stay out.
    """
    points: dict[date, float] = {}
    for issue in issues:
        if issue.now[fuel] is not None:
            points[issue.day] = issue.now[fuel] or 0.0
        nxt = issue.next_price[fuel]
        if nxt is not None and issue.next_effective is not None:
            points.setdefault(issue.next_effective, nxt)
    days = sorted(points)
    series = dict(points)
    for a, b in zip(days, days[1:], strict=False):
        if points[a] == points[b]:
            d = a + timedelta(days=1)
            while d < b:
                series[d] = points[a]
                d += timedelta(days=1)
    return series


def backfill(conn, issues: list[Issue]) -> int:
    """Write pinned-down max prices into the history for days that have none yet."""
    diesel = daily_max_prices(issues, "diesel")
    e10 = daily_max_prices(issues, "e10")
    written = 0
    for day in sorted(set(diesel) | set(e10)):
        existing = history.get(conn, day)
        d = None if existing and existing.diesel_max is not None else diesel.get(day)
        e = None if existing and existing.e10_max is not None else e10.get(day)
        if d is None and e is None:
            continue
        history.upsert(conn, DailyPrices(day=day, diesel_max=d, e10_max=e))
        written += 1
    return written


@dataclass(frozen=True)
class Scored:
    day: date
    fuel: str
    direction: str
    size_ct: float | None
    actual_ct: float  # price on the last forecast day minus price on the newsletter day
    correct: bool


def score(issues: list[Issue]) -> list[Scored]:
    """Score each real forecast: did the max price move that way by the last forecast day?

    A forecast of a change that the same newsletter already announced as the next max price
    (same fuel) is not a forecast and is skipped, as are forecasts without a day or without
    prices on both days.
    """
    series = {f: daily_max_prices(issues, f) for f in FUELS}
    scored = []
    for issue in issues:
        for fuel in FUELS:
            fc = issue.forecast[fuel]
            if fc is None or fc.last_day is None or issue.next_price[fuel] is not None:
                continue
            start = series[fuel].get(issue.day)
            end = series[fuel].get(fc.last_day)
            if start is None or end is None:
                continue
            delta = round((end - start) * 100, 1)
            kind = fc.direction.removesuffix("_conditional")
            if kind == "up":
                ok = delta > 0.05
            elif kind == "down":
                ok = delta < -0.05
            else:
                ok = abs(delta) <= 0.05
            scored.append(Scored(issue.day, fuel, fc.direction, fc.size_ct, delta, ok))
    return scored


def summarise(scored: list[Scored]) -> dict[str, str]:
    out = {}
    for fuel in (*FUELS, "all"):
        for conditional in (False, True):
            subset = [
                s
                for s in scored
                if (fuel == "all" or s.fuel == fuel)
                and s.direction.endswith("_conditional") == conditional
            ]
            if not subset:
                continue
            hit = sum(s.correct for s in subset)
            label = f"{fuel} {'conditional' if conditional else 'firm'}"
            out[label] = f"{hit}/{len(subset)} correct ({100 * hit / len(subset):.0f}%)"
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m fuelprices.newsletter")
    parser.add_argument("command", choices=["score", "backfill"])
    parser.add_argument("--csv", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--db", type=Path, default=history.DEFAULT_DB_PATH)
    args = parser.parse_args(argv)
    issues = load(args.csv)
    if args.command == "backfill":
        conn = history.connect(args.db)
        print(f"{backfill(conn, issues)} days written")
        return
    scored = score(issues)
    for label, text in summarise(scored).items():
        print(f"{label}: {text}")
    sized = [s for s in scored if s.size_ct is not None and s.correct]
    if sized:
        err = sum(abs(abs(s.actual_ct) - (s.size_ct or 0)) for s in sized) / len(sized)
        print(f"size error on {len(sized)} correct forecasts with a size: {err:.1f} cent/L")


if __name__ == "__main__":
    main()
