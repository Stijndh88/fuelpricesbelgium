import pytest

from fuelprices.products import ChangeRule, Product, match_product


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Essence 95 RON E10", Product.E10),
        ("Benzine 95 RON E10", Product.E10),
        ("Essence 98 RON E5", Product.E5_98),
        ("Diesel B7", Product.DIESEL_B7),
        ("Gasolie verwarming (H0/H7) (vanaf 2000 l)", Product.HEATING_OIL),
        ("Gasoil chauffage (H0/H7) (à partir de 2000 l)", Product.HEATING_OIL),
        ("Gasolie verwarming (H0/H7) (minder dan 2000 l)", Product.HEATING_OIL_SMALL),
        ("Gasoil chauffage (H0/H7) (moins de 2000 l)", Product.HEATING_OIL_SMALL),
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
