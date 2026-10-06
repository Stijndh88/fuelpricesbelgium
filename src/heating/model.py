"""Cost of one kWh of heat from a gas boiler versus a heat pump.

A gas boiler turns 1 kWh of gas into ``efficiency`` kWh of heat (about 0.9 for a condensing
boiler). A heat pump turns 1 kWh of electricity into ``COP`` kWh of heat, and its COP drops
as it gets colder outside. The heat pump is cheaper whenever its COP is above the break-even
COP, ``electricity price * boiler efficiency / gas price``.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field

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


# EN 14825 "average" heating season (Strasbourg): hours per outdoor temperature bin. Used to
# turn a datasheet SCOP into a COP curve. Design temperature -10 deg C, no heating from 16.
EN14825_AVERAGE_BINS: tuple[tuple[int, int], ...] = (
    (-10, 1), (-9, 25), (-8, 23), (-7, 24), (-6, 27), (-5, 68), (-4, 91), (-3, 89),
    (-2, 165), (-1, 173), (0, 240), (1, 280), (2, 320), (3, 357), (4, 356), (5, 303),
    (6, 330), (7, 326), (8, 348), (9, 335), (10, 315), (11, 215), (12, 169), (13, 151),
    (14, 105), (15, 74),
)  # fmt: skip


def seasonal_cop(curve: CopCurve) -> float:
    """The SCOP this COP curve gives over the EN 14825 average season.

    Heat need in each bin is proportional to (16 - T) times the hours; the SCOP is the total
    heat over the total electricity. Ignores part-load and backup-heater effects.
    """
    heat = sum(hours * (16 - t) for t, hours in EN14825_AVERAGE_BINS)
    electricity = sum(hours * (16 - t) / curve.cop(t) for t, hours in EN14825_AVERAGE_BINS)
    return heat / electricity


def scaled_to_scop(curve: CopCurve, scop: float) -> CopCurve:
    """The same curve shape, scaled so its seasonal COP matches a datasheet SCOP."""
    factor = scop / seasonal_cop(curve)
    return CopCurve(tuple((t, c * factor) for t, c in curve.points))


@dataclass(frozen=True)
class HeatPumpUnit:
    """One outdoor unit, from its datasheet: rated heating power at +7 and -10 deg C, SCOP."""

    name: str
    heating_kw: float
    heating_kw_at_minus10: float
    scop: float

    def capacity_kw(self, outdoor_temp: float) -> float:
        """Heating power available at this temperature, linear between -10 and +7 deg C."""
        if outdoor_temp >= 7:
            return self.heating_kw
        if outdoor_temp <= -10:
            return self.heating_kw_at_minus10
        span = self.heating_kw - self.heating_kw_at_minus10
        return self.heating_kw_at_minus10 + span * (outdoor_temp + 10) / 17


@dataclass(frozen=True)
class HeatPumpSystem:
    units: tuple[HeatPumpUnit, ...] = field(default_factory=tuple)

    def capacity_kw(self, outdoor_temp: float) -> float:
        return sum(u.capacity_kw(outdoor_temp) for u in self.units)

    @property
    def scop(self) -> float:
        """Combined SCOP: total rated heat over the electricity each unit needs for its share."""
        total = sum(u.heating_kw for u in self.units)
        return total / sum(u.heating_kw / u.scop for u in self.units)


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
    """One day's heating cost with only gas, and with the heat pumps first (gas tops up)."""

    outdoor_temp: float
    heat_kwh: float
    cop: float
    gas_eur: float
    heat_pump_eur: float
    heat_pump_share: float = 1.0  # part of the heat the heat pumps can deliver on their own

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
    capacity_kw: float | None = None,
) -> DayCost:
    """Cost of the day's heat. With ``capacity_kw``, the heat pumps deliver at most that much
    power around the clock and the gas boiler covers the rest."""
    heat = heat_demand_kwh(outdoor_temp, loss_kwh_per_degree_day, base_temp)
    cop = curve.cop(outdoor_temp)
    from_heat_pump = heat if capacity_kw is None else min(heat, capacity_kw * 24)
    gas_per_kwh = gas_cost_per_kwh_heat(prices, boiler_efficiency)
    return DayCost(
        outdoor_temp=outdoor_temp,
        heat_kwh=heat,
        cop=cop,
        gas_eur=heat * gas_per_kwh,
        heat_pump_eur=from_heat_pump * heat_pump_cost_per_kwh_heat(prices, cop)
        + (heat - from_heat_pump) * gas_per_kwh,
        heat_pump_share=from_heat_pump / heat if heat else 1.0,
    )


# Typical coldest hours of a heating month in Belgium (deg C). The capacity tariff bills the
# highest 15-minute power of each month, and the heat pumps draw most then. Months not listed
# have no heating and add nothing. Rough values, not measurements.
COLD_SPELL_TEMPS: dict[int, float] = {
    10: 1.0,
    11: -3.0,
    12: -6.0,
    1: -7.0,
    2: -6.0,
    3: -3.0,
    4: 0.0,
}


@dataclass(frozen=True)
class AnnualEstimate:
    """A normal year's heating cost with gas only versus heat pumps first (gas tops up)."""

    heat_kwh: float
    gas_only_eur: float
    heat_pump_eur: float  # electricity plus the gas still needed on the coldest hours
    electricity_kwh: float
    capacity_extra_kw: float  # yearly average rise of the monthly peak, heat pumps follow the load
    capacity_eur: float
    capacity_extra_kw_max: float  # same, with the heat pumps running flat out in the cold spell
    capacity_eur_max: float

    @property
    def saving_before_capacity_eur(self) -> float:
        return self.gas_only_eur - self.heat_pump_eur

    @property
    def net_saving_eur(self) -> float:
        return self.saving_before_capacity_eur - self.capacity_eur

    @property
    def net_saving_worst_eur(self) -> float:
        return self.saving_before_capacity_eur - self.capacity_eur_max


def annual_estimate(
    annual_heat_kwh: float,
    prices: Prices,
    curve: CopCurve,
    system: HeatPumpSystem,
    boiler_efficiency: float,
    capacity_eur_per_kw_year: float,
) -> AnnualEstimate:
    """Cost of a normal year over the EN 14825 temperature bins.

    The heat need is spread over the bins in proportion to (16 - T) times the hours. The heat
    pumps cover the load up to their available power, gas the rest. For the capacity tariff the
    heat pumps' electric power in each month's cold spell is added on top of the household's
    existing monthly peak, assuming that peak is above the 2.5 kW minimum and coincides with the
    heat pumps. Two figures: the heat pumps following the load, and (``_max``) running flat out,
    as when warming up a cold house.
    """
    degree_hours = sum(hours * (16 - t) for t, hours in EN14825_AVERAGE_BINS)
    kw_per_degree = annual_heat_kwh / degree_hours
    gas_per_kwh_heat = gas_cost_per_kwh_heat(prices, boiler_efficiency)
    electricity_kwh = electricity_eur = gas_eur = 0.0
    for t, hours in EN14825_AVERAGE_BINS:
        load_kw = kw_per_degree * (16 - t)
        from_heat_pump = min(load_kw, system.capacity_kw(t))
        electricity_kwh += hours * from_heat_pump / curve.cop(t)
        gas_eur += hours * (load_kw - from_heat_pump) * gas_per_kwh_heat
    electricity_eur = electricity_kwh * prices.electricity
    peaks, peaks_max = [], []
    for t in COLD_SPELL_TEMPS.values():
        load_kw = kw_per_degree * (16 - t)
        peaks.append(min(load_kw, system.capacity_kw(t)) / curve.cop(t))
        peaks_max.append(system.capacity_kw(t) / curve.cop(t))
    extra_kw, extra_kw_max = sum(peaks) / 12, sum(peaks_max) / 12
    return AnnualEstimate(
        heat_kwh=annual_heat_kwh,
        gas_only_eur=annual_heat_kwh * gas_per_kwh_heat,
        heat_pump_eur=electricity_eur + gas_eur,
        electricity_kwh=electricity_kwh,
        capacity_extra_kw=extra_kw,
        capacity_eur=extra_kw * capacity_eur_per_kw_year,
        capacity_extra_kw_max=extra_kw_max,
        capacity_eur_max=extra_kw_max * capacity_eur_per_kw_year,
    )
