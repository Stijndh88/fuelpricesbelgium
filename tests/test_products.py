import pytest

from fuelprices.products import ChangeRule, Product, match_product


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Essence 95 RON E10", Product.E10),
        ("Benzine 95 RON - E10", Product.E10),
        ("Essence 98 RON E5", Product.E5_98),
        ("Diesel B7", Product.DIESEL_B7),
        ("Gasoil diesel - B10", Product.DIESEL_B10),
        ("LPG (Autogas)", Product.LPG),
        ("Gasolie verwarming 50S (< 2000 l)", Product.HEATING_OIL),
        ("Pétrole lampant", None),
    ],
)
def test_match_product(name, expected):
    assert match_product(name) is expected


def test_heating_oil_follows_daily_rule():
    assert Product.HEATING_OIL.change_rule is ChangeRule.DAILY
    assert Product.DIESEL_B7.change_rule is ChangeRule.THRESHOLD


def test_from_code_round_trip():
    for product in Product:
        assert Product.from_code(product.code) is product
