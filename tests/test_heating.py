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


SECRETS = {
    "HEATING_LATITUDE": "51.2345",
    "HEATING_LONGITUDE": "4.4321",
    "HEATING_GAS_EUR_PER_KWH": "0.0987",
    "HEATING_ELECTRICITY_EUR_PER_KWH": "0.2876",
    "HEATING_ANNUAL_GAS_KWH": "23456",
    "HEATING_BOILER_EFFICIENCY": "0,87",
}


def test_env_overrides_settings_and_ignores_empty_values():
    env = {**SECRETS, "HEATING_HOT_WATER_SHARE": ""}  # unset secrets arrive as empty strings
    settings = config.with_env(config.load(), env)
    assert (settings.latitude, settings.longitude) == (51.2345, 4.4321)
    assert settings.annual_gas_kwh == 23456
    assert settings.boiler_efficiency == pytest.approx(0.87)
    assert settings.hot_water_share == config.Settings().hot_water_share
    assert config.uses_private_values(env)
    assert not config.uses_private_values({"HEATING_LATITUDE": ""})


def test_env_error_does_not_echo_the_value():
    with pytest.raises(ValueError) as e:
        config.env_value("HEATING_LATITUDE", {"HEATING_LATITUDE": "51.2345N"})
    assert "51.2345" not in str(e.value)


def run_cli(monkeypatch, capsys, extra=()):
    for name in config.PRIVATE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in SECRETS.items():
        monkeypatch.setenv(name, value)
    cli.main(
        ["--weather-json", str(FIXTURES / "open_meteo_sample.json"), "--day", "2026-10-06", *extra]
    )
    return capsys.readouterr().out


def test_report_hides_private_values_when_env_is_used(monkeypatch, capsys):
    out = run_cli(monkeypatch, capsys)
    assert "| day | mean temp °C | cheaper |" in out
    assert "capacity tariff included" in out
    for private in ("0.0987", "0.2876", "23456", "51.2345", "4.4321", "87%", "EUR", "kWh", "COP"):
        assert private not in out


def test_show_private_prints_the_full_report(monkeypatch, capsys):
    out = run_cli(monkeypatch, capsys, ["--show-private"])
    assert "0.0987" in out and "your own prices (environment)" in out
    assert "heat pump EUR" in out
    assert "Net saving over a year" in out and "Capacity tariff" in out


def make_system():
    return model.HeatPumpSystem(
        (
            model.HeatPumpUnit("a", heating_kw=4.2, heating_kw_at_minus10=2.7, scop=4.6),
            model.HeatPumpUnit("b", heating_kw=8.0, heating_kw_at_minus10=5.14, scop=4.32),
        )
    )


def test_annual_estimate_adds_up():
    curve = model.scaled_to_scop(model.CopCurve(), 4.4)
    year = model.annual_estimate(4000, PRICES, curve, make_system(), 0.9, 50.0)
    assert year.gas_only_eur == pytest.approx(4000 * 0.10 / 0.9)
    # All heat comes from the heat pumps (the house is small), so no gas is left over.
    assert year.electricity_kwh == pytest.approx(4000 / 4.4, rel=0.15)
    assert year.heat_pump_eur == pytest.approx(year.electricity_kwh * 0.30)
    assert year.capacity_eur == pytest.approx(year.capacity_extra_kw * 50.0)
    assert year.net_saving_eur == pytest.approx(
        year.gas_only_eur - year.heat_pump_eur - year.capacity_eur
    )
    assert 0 < year.capacity_extra_kw < year.capacity_extra_kw_max
    assert year.net_saving_worst_eur < year.net_saving_eur


def test_annual_estimate_gas_tops_up_when_the_house_needs_more_than_the_heat_pumps_give():
    curve = model.CopCurve(((-15.0, 2.0), (20.0, 4.0)))
    small = model.HeatPumpSystem((model.HeatPumpUnit("a", 1.0, 0.5, 4.0),))
    year = model.annual_estimate(20000, PRICES, curve, small, 0.9, 0.0)
    assert year.heat_pump_eur > year.electricity_kwh * 0.30  # gas bought on top
    assert year.capacity_eur == 0


def test_capacity_tariff_can_come_from_the_environment():
    settings = config.with_env(config.load(), {"HEATING_CAPACITY_EUR_PER_KW_YEAR": "53,13"})
    assert settings.capacity_eur_per_kw_year == pytest.approx(53.13)
    assert config.Settings().capacity_eur_per_kw_year == 55.0
