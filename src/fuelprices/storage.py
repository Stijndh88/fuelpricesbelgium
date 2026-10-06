"""Price history kept as a plain CSV file, one row per product per day a price took effect."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from fuelprices.models import PriceRecord
from fuelprices.products import Product

FIELDS = ["valid_from", "product", "price_eur_per_litre", "source"]


def load_history(path: Path) -> list[PriceRecord]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [
            PriceRecord(
                valid_from=date.fromisoformat(row["valid_from"]),
                product=Product.from_code(row["product"]),
                price_eur_per_litre=float(row["price_eur_per_litre"]),
                source=row["source"],
            )
            for row in csv.DictReader(f)
        ]


def merge(existing: Iterable[PriceRecord], new: Iterable[PriceRecord]) -> list[PriceRecord]:
    """Combine records, letting ``new`` win for the same day and product, sorted by day."""
    by_key = {(r.valid_from, r.product): r for r in existing}
    for record in new:
        by_key[(record.valid_from, record.product)] = record
    return sorted(by_key.values(), key=lambda r: (r.valid_from, r.product.code))


def save_history(path: Path, records: Iterable[PriceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "valid_from": r.valid_from.isoformat(),
                    "product": r.product.code,
                    "price_eur_per_litre": f"{r.price_eur_per_litre:.4f}",
                    "source": r.source,
                }
            )


def update_history(path: Path, new: Iterable[PriceRecord]) -> list[PriceRecord]:
    """Merge ``new`` into the history file at ``path`` and return the full history."""
    records = merge(load_history(path), new)
    save_history(path, records)
    return records
