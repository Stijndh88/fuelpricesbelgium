"""Facts extracted from the Energieprijzen.vlaanderen newsletter.

The file is ``data/newsletter_predictions.csv``.

The newsletter states the official maximum price valid today, the one published for the next
change, and a forecast of the next price change. Only those numbers are stored, never newsletter
text. This module loads the file and scores the forecasts against the official maximum prices in
``data/prices.sqlite``. It can also check the prices the issues state against that history.

Run ``python -m fuelprices.newsletter score`` or ``... check``.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fuelprices import history

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


def official_series(conn: sqlite3.Connection, fuel: str) -> dict[date, float]:
    """Official max price per day from the history, for days that have one."""
    column = f"{fuel}_max"
    return {
        r.day: getattr(r, column)
        for r in history.all_rows(conn)
        if getattr(r, column) is not None
    }


def check(issues: list[Issue], official: dict[str, dict[date, float]]) -> list[tuple]:
    """Stated max prices (today's, or the next one from its start day) that differ from history."""
    off_by = []
    for issue in issues:
        for fuel in FUELS:
            stated = [(issue.day, issue.now[fuel])]
            if issue.next_effective:
                stated.append((issue.next_effective, issue.next_price[fuel]))
            for day, price in stated:
                known = official[fuel].get(day)
                if price is not None and known is not None and abs(price - known) > 0.0006:
                    off_by.append((issue.day, fuel, day, price, known))
    return off_by


@dataclass(frozen=True)
class Scored:
    day: date
    fuel: str
    direction: str
    size_ct: float | None
    actual_ct: float  # price on the last forecast day minus price on the newsletter day
    correct: bool


def score(issues: list[Issue], official: dict[str, dict[date, float]]) -> list[Scored]:
    """Score each real forecast: did the max price move that way by the last forecast day?

    A forecast of a change that the same newsletter already announced as the next max price
    (same fuel) is not a forecast and is skipped, as are forecasts without a day or without
    prices on both days.
    """
    scored = []
    for issue in issues:
        for fuel in FUELS:
            fc = issue.forecast[fuel]
            if fc is None or fc.last_day is None or issue.next_price[fuel] is not None:
                continue
            start = official[fuel].get(issue.day)
            end = official[fuel].get(fc.last_day)
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
    parser.add_argument("command", choices=["score", "check"])
    parser.add_argument("--csv", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--db", type=Path, default=history.DEFAULT_DB_PATH)
    args = parser.parse_args(argv)
    issues = load(args.csv)
    conn = history.connect(args.db)
    official = {f: official_series(conn, f) for f in FUELS}
    if args.command == "check":
        for issue_day, fuel, day, stated, known in check(issues, official):
            print(f"{issue_day} {fuel} {day}: newsletter {stated:.3f}, history {known:.3f}")
        return
    scored = score(issues, official)
    for label, text in summarise(scored).items():
        print(f"{label}: {text}")
    sized = [s for s in scored if s.size_ct is not None and s.correct]
    if sized:
        err = sum(abs(abs(s.actual_ct) - (s.size_ct or 0)) for s in sized) / len(sized)
        print(f"size error on {len(sized)} correct forecasts with a size: {err:.1f} cent/L")


if __name__ == "__main__":
    main()
