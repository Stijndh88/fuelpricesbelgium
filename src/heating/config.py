"""Settings for the heating comparison, read from a TOML file (see config/heating.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from heating.model import DEFAULT_COP_CURVE, CopCurve, loss_from_annual_gas

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
    curve = heat_pump.get("cop_curve")
    return Settings(
        latitude=location.get("latitude", defaults.latitude),
        longitude=location.get("longitude", defaults.longitude),
        boiler_efficiency=boiler.get("efficiency", defaults.boiler_efficiency),
        annual_gas_kwh=house.get("annual_gas_kwh", defaults.annual_gas_kwh),
        hot_water_share=house.get("hot_water_share", defaults.hot_water_share),
        base_temp=house.get("base_temp", defaults.base_temp),
        degree_days=house.get("degree_days", defaults.degree_days),
        cop_curve=CopCurve(tuple((float(t), float(c)) for t, c in curve))
        if curve
        else defaults.cop_curve,
    )
