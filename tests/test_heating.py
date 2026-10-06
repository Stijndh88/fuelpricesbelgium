from datetime import date
from pathlib import Path

import pytest

from heating import __main__ as cli
from heating import config, model, tariffs, weather

FIXTURES = Path(__file__).parent / "fixtures"
PRICES = model.Prices(gas=0.10, electricity=0.30)


def test_cop_curve_interpolates_and_is_flat_beyond_the_ends():
    curve = model.CopCurve(((-7.0, 2.0), (7.0, 4.0)))
    assert curve.cop(0.0) == pytest.approx(3.0)
    assert curve.cop(-20.0) == 2.0
    assert curve.cop(30.0) == 4.0


def test_cop_curve_temperature_for_inverts_cop():
    curve = model.CopCurve(((-7.0, 2.0), (7.0, 4.0)))
    assert curve.temperature_for(3.0) == pytest.approx(0.0)
    assert curve.temperature_for(1.5) is None  # heat pump always cheaper
    assert curve.temperature_for(5.0) is None  # never cheaper


def test_cop_curve_rejects_unsorted_points():
    with pytest.raises(ValueError):
        model.CopCurve(((7.0, 4.0), (-7.0, 2.0)))


def test_break_even_cop():
    # 0.30 EUR/kWh electricity vs 0.10 gas through a 90 % boiler: COP 2.7 breaks even.
    assert model.break_even_cop(PRICES, 0.9) == pytest.approx(2.7)


def test_day_cost_picks_the_cheaper_option():
    curve = model.CopCurve(((-7.0, 2.0), (7.0, 4.0)))
    warm = model.day_cost(7.0, PRICES, curve, 0.9, loss_kwh_per_degree_day=10, base_temp=16.5)
    assert warm.heat_kwh == pytest.approx(95)
    assert warm.gas_eur == pytest.approx(95 * 0.10 / 0.9)
    assert warm.heat_pump_eur == pytest.approx(95 * 0.30 / 4.0)
    assert warm.cheaper == "heat pump"
    cold = model.day_cost(-7.0, PRICES, curve, 0.9, loss_kwh_per_degree_day=10, base_temp=16.5)
    assert cold.cheaper == "gas"
    mild = model.day_cost(18.0, PRICES, curve, 0.9, loss_kwh_per_degree_day=10, base_temp=16.5)
    assert mild.heat_kwh == 0


def test_loss_from_annual_gas():
    assert model.loss_from_annual_gas(20000, 0.9, 0.1, 2400) == pytest.approx(6.75)


def test_tariff_for_day_takes_latest_month(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text(
        "# comment\nmonth,gas_eur_per_kwh,electricity_eur_per_kwh,source\n"
        "2026-10,0.12,0.30,b\n2026-09,0.10,0.31,a\n",
        encoding="utf-8",
    )
    loaded = tariffs.load(path)
    assert tariffs.for_day(loaded, date(2026, 9, 30)).source == "a"
    assert tariffs.for_day(loaded, date(2026, 10, 1)).prices == model.Prices(0.12, 0.30)
    with pytest.raises(LookupError):
        tariffs.for_day(loaded, date(2026, 8, 31))


def test_weather_parse_skips_missing_days():
    temps = weather.parse((FIXTURES / "open_meteo_sample.json").read_text(encoding="utf-8"))
    assert temps[date(2026, 10, 8)] == -2.5
    assert date(2026, 10, 9) not in temps


def test_repo_config_and_tariffs_load():
    settings = config.load()
    assert settings.cop_curve.cop(7) == pytest.approx(3.9)
    assert tariffs.load()


def test_cli_report_offline(capsys):
    cli.main(
        [
            "--weather-json",
            str(FIXTURES / "open_meteo_sample.json"),
            "--day",
            "2026-10-06",
            "--gas-price",
            "0.10",
            "--electricity-price",
            "0.30",
        ]
    )
    out = capsys.readouterr().out
    assert "COP is above **2.70**" in out
    assert "scenario from the command line" in out
    assert "| Tue 06/10 | 9.8 |" in out
    assert "Mon 05/10" not in out  # past days are left out
