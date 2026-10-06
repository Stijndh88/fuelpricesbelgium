from datetime import date
from pathlib import Path

import pytest

from fuelprices.products import Product
from fuelprices.sources import fod

SAMPLE = (Path(__file__).parent / "fixtures" / "fod_sample.html").read_text(encoding="utf-8")


def test_parse_sample_page():
    records = {r.product: r for r in fod.parse(SAMPLE)}
    assert set(records) == set(Product)
    assert records[Product.DIESEL_B7].price_eur_per_litre == 2.392
    assert records[Product.E10].price_eur_per_litre == 2.065
    assert records[Product.LPG].price_eur_per_litre == 0.861
    assert all(r.valid_from == date(2026, 10, 7) for r in records.values())
    assert all(r.source == "fod-economie" for r in records.values())


def test_explicit_date_wins():
    records = fod.parse(SAMPLE, valid_from=date(2026, 1, 1))
    assert {r.valid_from for r in records} == {date(2026, 1, 1)}


def test_layout_change_is_reported():
    with pytest.raises(ValueError, match="layout"):
        fod.parse("<html><p>Onderhoud</p></html>")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("2,0650 €", 2.065), ("2.392", 2.392), ("1 234,00", None), ("15,20", None)],
)
def test_parse_price(text, expected):
    assert fod.parse_price(text) == expected


def test_parse_date_formats():
    assert fod.parse_date("vanaf 07/10/2026") == date(2026, 10, 7)
    assert fod.parse_date("à partir du 2026-10-02") == date(2026, 10, 2)
