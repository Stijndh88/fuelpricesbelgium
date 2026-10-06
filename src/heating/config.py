"""Settings for the heating comparison, read from a TOML file (see config/heating.toml)."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from heating.model import (
    DEFAULT_COP_CURVE,
    CopCurve,
    HeatPumpSystem,
    HeatPumpUnit,
    loss_from_annual_gas,
    scaled_to_scop,
)

DEFAULT_CONFIG_PATH = Path("config/heating.toml")


@dataclass(frozen=True)
class Settings:
    latitude: float = 50.85
    longitude: float = 4.35
    boiler_efficiency: float = 0.9
    annual_gas_kwh: float = 17000
    hot_water_share: float = 0.15
    base_temp: float = 16.5
    degree_days: float = 2400
    cop_curve: CopCurve = CopCurve(DEFAULT_COP_CURVE)
    heat_pumps: HeatPumpSystem = HeatPumpSystem()

    @property
    def capacity_known(self) -> bool:
        return bool(self.heat_pumps.units)

    @property
    def loss_kwh_per_degree_day(self) -> float:
        return loss_from_annual_gas(
            self.annual_gas_kwh, self.boiler_efficiency, self.hot_water_share, self.degree_days
        )


def load(path: str | Path = DEFAULT_CONFIG_PATH) -> Settings:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    location, boiler = raw.get("location", {}), raw.get("boiler", {})
    house, heat_pump = raw.get("house", {}), raw.get("heat_pump", {})
    defaults = Settings()
    units = HeatPumpSystem(
        tuple(
            HeatPumpUnit(
                name=u["name"],
                heating_kw=u["heating_kw"],
                heating_kw_at_minus10=u["heating_kw_at_minus10"],
                scop=u["scop"],
            )
            for u in heat_pump.get("units", [])
        )
    )
    curve = heat_pump.get("cop_curve")
    if curve:
        cop_curve = CopCurve(tuple((float(t), float(c)) for t, c in curve))
    elif units.units:
        # No measured curve: take the generic shape and scale it to the units' SCOP.
        cop_curve = scaled_to_scop(defaults.cop_curve, units.scop)
    else:
        cop_curve = defaults.cop_curve
    return Settings(
        latitude=location.get("latitude", defaults.latitude),
        longitude=location.get("longitude", defaults.longitude),
        boiler_efficiency=boiler.get("efficiency", defaults.boiler_efficiency),
        annual_gas_kwh=house.get("annual_gas_kwh", defaults.annual_gas_kwh),
        hot_water_share=house.get("hot_water_share", defaults.hot_water_share),
        base_temp=house.get("base_temp", defaults.base_temp),
        degree_days=house.get("degree_days", defaults.degree_days),
        cop_curve=cop_curve,
        heat_pumps=units,
    )


# Personal values can come from environment variables instead of the config file, so they
# never have to be committed. In GitHub Actions they are repository secrets.
ENV_LATITUDE = "HEATING_LATITUDE"
ENV_LONGITUDE = "HEATING_LONGITUDE"
ENV_GAS_PRICE = "HEATING_GAS_EUR_PER_KWH"
ENV_ELECTRICITY_PRICE = "HEATING_ELECTRICITY_EUR_PER_KWH"
ENV_ANNUAL_GAS_KWH = "HEATING_ANNUAL_GAS_KWH"
ENV_BOILER_EFFICIENCY = "HEATING_BOILER_EFFICIENCY"
ENV_HOT_WATER_SHARE = "HEATING_HOT_WATER_SHARE"
PRIVATE_ENV_VARS = (
    ENV_LATITUDE,
    ENV_LONGITUDE,
    ENV_GAS_PRICE,
    ENV_ELECTRICITY_PRICE,
    ENV_ANNUAL_GAS_KWH,
    ENV_BOILER_EFFICIENCY,
    ENV_HOT_WATER_SHARE,
)


def env_value(name: str, env: Mapping[str, str] | None = None) -> float | None:
    """A number from the environment, None when unset or empty. Never echoes a bad value."""
    raw = (os.environ if env is None else env).get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        raise ValueError(f"{name} is set but is not a number") from None


def uses_private_values(env: Mapping[str, str] | None = None) -> bool:
    return any(env_value(name, env) is not None for name in PRIVATE_ENV_VARS)


def with_env(settings: Settings, env: Mapping[str, str] | None = None) -> Settings:
    """Settings with the personal values from the environment applied on top."""
    overrides = {
        "latitude": env_value(ENV_LATITUDE, env),
        "longitude": env_value(ENV_LONGITUDE, env),
        "annual_gas_kwh": env_value(ENV_ANNUAL_GAS_KWH, env),
        "boiler_efficiency": env_value(ENV_BOILER_EFFICIENCY, env),
        "hot_water_share": env_value(ENV_HOT_WATER_SHARE, env),
    }
    return replace(settings, **{k: v for k, v in overrides.items() if v is not None})
