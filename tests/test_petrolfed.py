from datetime import date
from pathlib import Path

from fuelprices.products import Product
from fuelprices.sources import petrolfed

FIXTURE = Path(__file__).parent / "fixtures" / "petrolfed_export.json"


def test_parse_keeps_diesel_and_e10_with_a_price_for_every_day():
    series = petrolfed.parse(FIXTURE.read_text(encoding="utf-8"))
    assert set(series) == {Product.DIESEL_B7, Product.E10}
    assert series[Product.DIESEL_B7] == {
        date(2026, 10, 5): 2.432,
        date(2026, 10, 6): 2.432,
        date(2026, 10, 7): 2.392,
    }


def test_to_records_is_sorted_per_product():
    records = petrolfed.to_records(petrolfed.parse(FIXTURE.read_text(encoding="utf-8")))
    diesel = [r for r in records if r.product is Product.DIESEL_B7]
    assert [r.valid_from for r in diesel] == sorted(r.valid_from for r in diesel)
    assert {r.source for r in records} == {"petrolfed"}
