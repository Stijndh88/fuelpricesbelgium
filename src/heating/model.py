"""Cost of one kWh of heat from a gas boiler versus a heat pump.

A gas boiler turns 1 kWh of gas into ``efficiency`` kWh of heat (about 0.9 for a condensing
boiler). A heat pump turns 1 kWh of electricity into ``COP`` kWh of heat, and its COP drops
as it gets colder outside. The heat pump is cheaper whenever its COP is above the break-even
COP, ``electricity price * boiler efficiency / gas price``.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

# Typical air-to-air heat pump (split airco unit) COP by outdoor temperature (deg C). Generic
# values in the range of EN 14511 datasheets; replace them with your own unit's datasheet.
DEFAULT_COP_CURVE: tuple[tuple[float, float], ...] = (
    (-15.0, 1.8),
    (-7.0, 2.4),
    (2.0, 3.1),
    (7.0, 3.9),
    (12.0, 4.6),
    (20.0, 5.2),
)


@dataclass(frozen=True)
class CopCurve:
    """COP as a piecewise-linear function of outdoor temperature, flat beyond the ends."""

    points: tuple[tuple[float, float], ...] = DEFAULT_COP_CURVE

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("a COP curve needs at least two points")
        temps = [t for t, _ in self.points]
        if temps != sorted(temps) or len(set(temps)) != len(temps):
            raise ValueError("COP curve temperatures must be strictly increasing")

    def cop(self, outdoor_temp: float) -> float:
        temps = [t for t, _ in self.points]
        if outdoor_temp <= temps[0]:
            return self.points[0][1]
        if outdoor_temp >= temps[-1]:
            return self.points[-1][1]
        i = bisect_left(temps, outdoor_temp)
        (t0, c0), (t1, c1) = self.points[i - 1], self.points[i]
        return c0 + (c1 - c0) * (outdoor_temp - t0) / (t1 - t0)

    def temperature_for(self, cop: float) -> float | None:
        """Outdoor temperature at which the COP equals ``cop``, assuming COP rises with it.

        None when the curve never reaches ``cop`` (heat pump always or never cheaper).
        """
        if cop <= self.points[0][1] or cop > self.points[-1][1]:
            return None
        for (t0, c0), (t1, c1) in zip(self.points, self.points[1:], strict=False):
            if c0 <= cop <= c1 and c1 > c0:
                return t0 + (t1 - t0) * (cop - c0) / (c1 - c0)
        return None


@dataclass(frozen=True)
class Prices:
    """All-in variable prices (energy, network, taxes, VAT), EUR per kWh."""

    gas: float
    electricity: float


def gas_cost_per_kwh_heat(prices: Prices, boiler_efficiency: float) -> float:
    return prices.gas / boiler_efficiency


def heat_pump_cost_per_kwh_heat(prices: Prices, cop: float) -> float:
    return prices.electricity / cop


def break_even_cop(prices: Prices, boiler_efficiency: float) -> float:
    """The COP above which the heat pump is cheaper than gas."""
    return prices.electricity * boiler_efficiency / prices.gas


@dataclass(frozen=True)
class DayCost:
    outdoor_temp: float
    heat_kwh: float
    cop: float
    gas_eur: float
    heat_pump_eur: float

    @property
    def cheaper(self) -> str:
        return "heat pump" if self.heat_pump_eur < self.gas_eur else "gas"

    @property
    def saving_eur(self) -> float:
        return abs(self.gas_eur - self.heat_pump_eur)


def heat_demand_kwh(outdoor_temp: float, loss_kwh_per_degree_day: float, base_temp: float) -> float:
    """Heat the house needs on a day with this mean outdoor temperature (degree-day method)."""
    return loss_kwh_per_degree_day * max(0.0, base_temp - outdoor_temp)


def loss_from_annual_gas(
    annual_gas_kwh: float, boiler_efficiency: float, hot_water_share: float, degree_days: float
) -> float:
    """Estimate the house's heat need per degree-day from a year's gas use on the bill."""
    return annual_gas_kwh * (1 - hot_water_share) * boiler_efficiency / degree_days


def day_cost(
    outdoor_temp: float,
    prices: Prices,
    curve: CopCurve,
    boiler_efficiency: float,
    loss_kwh_per_degree_day: float,
    base_temp: float,
) -> DayCost:
    heat = heat_demand_kwh(outdoor_temp, loss_kwh_per_degree_day, base_temp)
    cop = curve.cop(outdoor_temp)
    return DayCost(
        outdoor_temp=outdoor_temp,
        heat_kwh=heat,
        cop=cop,
        gas_eur=heat * gas_cost_per_kwh_heat(prices, boiler_efficiency),
        heat_pump_eur=heat * heat_pump_cost_per_kwh_heat(prices, cop),
    )
