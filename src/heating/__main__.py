"""Print whether gas or the heat pump is cheaper, today and for the coming week.

Run with ``python -m heating``. Prices come from data/heating_tariffs.csv (override them with
--gas-price / --electricity-price to try a scenario), the house and equipment from
config/heating.toml, and the outdoor temperature from Open-Meteo. Output is Markdown.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

from heating import config, model, tariffs, weather


def report(
    settings: config.Settings,
    tariff: tariffs.Tariff,
    temps: dict[date, float],
    today: date,
) -> str:
    prices = tariff.prices
    eta = settings.boiler_efficiency
    gas_heat = model.gas_cost_per_kwh_heat(prices, eta)
    cop_needed = model.break_even_cop(prices, eta)
    switch = settings.cop_curve.temperature_for(cop_needed)

    lines = [
        f"## Heating: gas or heat pump ({today})",
        "",
        f"Tariff from {tariff.month:%Y-%m} ({tariff.source or 'no source given'}): "
        f"gas {prices.gas:.4f} EUR/kWh, electricity {prices.electricity:.4f} EUR/kWh.",
        "",
        f"- Heat from gas costs {gas_heat:.3f} EUR/kWh (boiler efficiency {eta:.0%}).",
    ]
    if settings.capacity_known:
        system = settings.heat_pumps
        lines.append(
            f"- Heat pumps ({', '.join(u.name for u in system.units)}): "
            f"{system.capacity_kw(7):.1f} kW at +7 °C, {system.capacity_kw(-10):.1f} kW at "
            f"-10 °C, combined SCOP {system.scop:.2f}. When the house needs more, gas tops up."
        )
    lines.append(f"- The heat pump is cheaper whenever its COP is above **{cop_needed:.2f}**.")
    if switch is not None:
        lines.append(
            f"- With your COP curve that is when the daily mean outdoor temperature is above "
            f"**{switch:.1f} °C**; below it, gas is cheaper."
        )
    elif cop_needed <= settings.cop_curve.points[0][1]:
        lines.append("- With your COP curve the heat pump is cheaper at every temperature.")
    else:
        lines.append("- With your COP curve gas is cheaper at every temperature.")

    days = sorted(d for d in temps if d >= today)
    if days:
        lines += [
            "",
            "| day | mean temp °C | COP | heat kWh | gas EUR | heat pump EUR | cheaper |"
            + (" heat pumps cover |" if settings.capacity_known else ""),
            "|---|---:|---:|---:|---:|---:|---|" + ("---:|" if settings.capacity_known else ""),
        ]
        total_gas = total_hp = total_best = 0.0
        for day in days:
            cost = model.day_cost(
                temps[day],
                prices,
                settings.cop_curve,
                eta,
                settings.loss_kwh_per_degree_day,
                settings.base_temp,
                settings.heat_pumps.capacity_kw(temps[day]) if settings.capacity_known else None,
            )
            total_gas += cost.gas_eur
            total_hp += cost.heat_pump_eur
            total_best += min(cost.gas_eur, cost.heat_pump_eur)
            cheaper = cost.cheaper if cost.heat_kwh else "no heating needed"
            lines.append(
                f"| {day:%a %d/%m} | {cost.outdoor_temp:.1f} | {cost.cop:.1f} | "
                f"{cost.heat_kwh:.0f} | {cost.gas_eur:.2f} | {cost.heat_pump_eur:.2f} | {cheaper} |"
                + (f" {cost.heat_pump_share:.0%} |" if settings.capacity_known else "")
            )
        lines += [
            "",
            f"Over these {len(days)} days: all gas {total_gas:.2f} EUR, heat pump first "
            f"{total_hp:.2f} EUR, switching each day to the cheaper one {total_best:.2f} EUR.",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_PATH)
    parser.add_argument("--tariffs", type=Path, default=tariffs.DEFAULT_TARIFFS_PATH)
    parser.add_argument("--gas-price", type=float, help="all-in EUR/kWh, overrides the tariff")
    parser.add_argument("--electricity-price", type=float, help="all-in EUR/kWh, overrides")
    parser.add_argument("--weather-json", type=Path, help="saved Open-Meteo response")
    parser.add_argument("--day", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)

    settings = config.load(args.config)
    tariff = tariffs.for_day(tariffs.load(args.tariffs), args.day)
    if args.gas_price or args.electricity_price:
        prices = replace(
            tariff.prices,
            gas=args.gas_price or tariff.prices.gas,
            electricity=args.electricity_price or tariff.prices.electricity,
        )
        tariff = replace(tariff, prices=prices, source="scenario from the command line")

    if args.weather_json:
        temps = weather.parse(args.weather_json.read_text(encoding="utf-8"))
    else:
        try:
            temps = weather.fetch_daily_means(settings.latitude, settings.longitude)
        except OSError as e:
            print(f"(no weather forecast: {e})", file=sys.stderr)
            temps = {}
    sys.stdout.write(report(settings, tariff, temps, args.day))
    return 0


if __name__ == "__main__":
    sys.exit(main())
