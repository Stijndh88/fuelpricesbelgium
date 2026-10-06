from datetime import date

from fuelprices import storage
from fuelprices.models import PriceRecord
from fuelprices.products import Product


def rec(day, product, price):
    return PriceRecord(date(2026, 10, day), product, price, "test")


def test_round_trip_and_merge(tmp_path):
    path = tmp_path / "prices.csv"
    storage.update_history(path, [rec(2, Product.DIESEL_B7, 2.432), rec(2, Product.E10, 2.065)])
    history = storage.update_history(
        path, [rec(7, Product.DIESEL_B7, 2.392), rec(2, Product.E10, 2.066)]
    )

    assert history == storage.load_history(path)
    assert [(r.valid_from.day, r.product, r.price_eur_per_litre) for r in history] == [
        (2, Product.DIESEL_B7, 2.432),
        (2, Product.E10, 2.066),
        (7, Product.DIESEL_B7, 2.392),
    ]


def test_missing_file_is_empty(tmp_path):
    assert storage.load_history(tmp_path / "nope.csv") == []
