"""Monthly all-in gas and electricity tariffs, kept in a small CSV.

Variable Belgian contracts change price once a month (gas follows TTF 101 / ZTP 101,
electricity Endex or EPEX), so one row per month is enough. Each row applies from its month
until a later row takes over.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from heating.model import Prices

DEFAULT_TARIFFS_PATH = Path("data/heating_tariffs.csv")


@dataclass(frozen=True)
class Tariff:
    month: date  # first day of the month the tariff starts
    prices: Prices
    source: str


def load(path: str | Path = DEFAULT_TARIFFS_PATH) -> list[Tariff]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [
            Tariff(
                month=date.fromisoformat(r["month"] + "-01"),
                prices=Prices(
                    gas=float(r["gas_eur_per_kwh"]),
                    electricity=float(r["electricity_eur_per_kwh"]),
                ),
                source=r.get("source", "").strip(),
            )
            for r in csv.DictReader(line for line in f if not line.startswith("#"))
        ]
    return sorted(rows, key=lambda t: t.month)


def for_day(tariffs: list[Tariff], day: date) -> Tariff:
    """The tariff in force on ``day``: the latest one starting on or before it."""
    current = [t for t in tariffs if t.month <= day]
    if not current:
        raise LookupError(f"no tariff on or before {day}")
    return current[-1]
