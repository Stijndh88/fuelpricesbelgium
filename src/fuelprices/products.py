"""Products that have an official maximum price in Belgium."""

from __future__ import annotations

import re
import unicodedata
from enum import Enum


class ChangeRule(Enum):
    """How the maximum price of a product is allowed to move (see ``fuelprices.rules``)."""

    THRESHOLD = "threshold"  # only when the product cost leaves a band around its base value
    DAILY = "daily"  # follows the product cost every working day, no thresholds


class Product(Enum):
    """A fuel with an official maximum price, with the rule that governs its changes."""

    E10 = ("e10", "Benzine 95 RON E10", ChangeRule.THRESHOLD)
    E5_98 = ("e5_98", "Benzine 98 RON E5", ChangeRule.THRESHOLD)
    DIESEL_B7 = ("diesel_b7", "Diesel B7", ChangeRule.THRESHOLD)
    DIESEL_B10 = ("diesel_b10", "Diesel B10", ChangeRule.THRESHOLD)
    LPG = ("lpg", "LPG", ChangeRule.THRESHOLD)
    HEATING_OIL = ("heating_oil", "Gasolie verwarming", ChangeRule.DAILY)

    def __init__(self, code: str, label: str, change_rule: ChangeRule) -> None:
        self.code = code
        self.label = label
        self.change_rule = change_rule

    @classmethod
    def from_code(cls, code: str) -> Product:
        for product in cls:
            if product.code == code:
                return product
        raise ValueError(f"unknown product code: {code!r}")


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


# Patterns matched against normalised product names as published by FOD Economie
# (Dutch or French). Order matters: the first match wins.
_NAME_PATTERNS: list[tuple[re.Pattern[str], Product]] = [
    (re.compile(r"\b95\b.*\be10\b"), Product.E10),
    (re.compile(r"\b98\b.*\be5\b"), Product.E5_98),
    (re.compile(r"\b(diesel|gasoil|gasolie)\b.*\bb10\b"), Product.DIESEL_B10),
    (re.compile(r"\b(diesel|gasoil|gasolie)\b.*\bb7\b"), Product.DIESEL_B7),
    (re.compile(r"\b(lpg|autogas)\b"), Product.LPG),
    (re.compile(r"\b(verwarming|chauffage)\b"), Product.HEATING_OIL),
]


def match_product(name: str) -> Product | None:
    """Map a published product name to a :class:`Product`, or ``None`` if it is not tracked."""
    normalised = _normalise(name)
    for pattern, product in _NAME_PATTERNS:
        if pattern.search(normalised):
            return product
    return None
