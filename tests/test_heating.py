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
    assert settings.cop_curve.cop(7) > 3.9
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


def test_scaled_curve_matches_the_scop():
    curve = model.scaled_to_scop(model.CopCurve(), 4.4)
    assert model.seasonal_cop(curve) == pytest.approx(4.4)
    assert curve.cop(-7) < curve.cop(7)


def test_heat_pump_system_capacity_and_scop():
    system = model.HeatPumpSystem(
        (
            model.HeatPumpUnit("a", heating_kw=4.2, heating_kw_at_minus10=2.7, scop=4.6),
            model.HeatPumpUnit("b", heating_kw=8.0, heating_kw_at_minus10=5.14, scop=4.32),
        )
    )
    assert system.capacity_kw(10) == pytest.approx(12.2)
    assert system.capacity_kw(-15) == pytest.approx(7.84)
    assert system.capacity_kw(-1.5) == pytest.approx((12.2 + 7.84) / 2)
    assert system.scop == pytest.approx(12.2 / (4.2 / 4.6 + 8.0 / 4.32))


def test_gas_tops_up_when_heat_pumps_fall_short():
    curve = model.CopCurve(((-7.0, 2.0), (7.0, 4.0)))
    # 100 kWh needed at 0 deg C, heat pumps deliver at most 2 kW x 24 h = 48 kWh at COP 3.
    cost = model.day_cost(0.0, PRICES, curve, 0.9, 100 / 16.5, 16.5, capacity_kw=2.0)
    assert cost.heat_pump_share == pytest.approx(0.48)
    assert cost.heat_pump_eur == pytest.approx(48 * 0.30 / 3 + 52 * 0.10 / 0.9)


def test_repo_config_has_the_samsung_units():
    settings = config.load()
    assert [u.name.split()[1] for u in settings.heat_pumps.units] == ["AJ040", "AJ068"]
    assert model.seasonal_cop(settings.cop_curve) == pytest.approx(settings.heat_pumps.scop)
