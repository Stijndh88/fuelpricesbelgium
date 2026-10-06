"""Data records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fuelprices.products import Product


@dataclass(frozen=True)
class PriceRecord:
    """The official maximum price of one product, valid from ``valid_from`` on."""

    valid_from: date
    product: Product
    price_eur_per_litre: float
    source: str
