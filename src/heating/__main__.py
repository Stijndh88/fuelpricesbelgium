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


def private_report(
    settings: config.Settings,
    tariff: tariffs.Tariff,
    temps: dict[date, float],
    today: date,
) -> str:
    """The advice without any figure that reveals personal values (for public logs).

    Leaves out prices, boiler, gas use, location, kWh and euro amounts, and the break-even COP
    (it gives away the price ratio). Only the verdict remains: the switch temperature and which
    option is cheaper each day.
    """
    prices = tariff.prices
    switch = settings.cop_curve.temperature_for(
        model.break_even_cop(prices, settings.boiler_efficiency)
    )
    if switch is not None:
        verdict = f"the heat pumps are cheaper when the daily mean is above **{switch:.1f} °C**"
    elif (
        model.break_even_cop(prices, settings.boiler_efficiency) <= settings.cop_curve.points[0][1]
    ):
        verdict = "the heat pumps are cheaper at every temperature"
    else:
        verdict = "gas is cheaper at every temperature"
    lines = [
        f"## Heating: gas or heat pump ({today})",
        "",
        "Calculated with personal values kept out of this page; run locally with `--show-private`"
        " for prices and euro amounts.",
        "",
        f"- With your prices and your units, {verdict}.",
    ]
    days = sorted(d for d in temps if d >= today)
    if days:
        lines += ["", "| day | mean temp °C | cheaper |", "|---|---:|---|"]
        for day in days:
            cost = model.day_cost(
                temps[day],
                prices,
                settings.cop_curve,
                settings.boiler_efficiency,
                settings.loss_kwh_per_degree_day,
                settings.base_temp,
                settings.heat_pumps.capacity_kw(temps[day]) if settings.capacity_known else None,
            )
            cheaper = cost.cheaper if cost.heat_kwh else "no heating needed"
            lines.append(f"| {day:%a %d/%m} | {cost.outdoor_temp:.1f} | {cheaper} |")
    return "\n".join(lines) + "\n"


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
    parser.add_argument(
        "--show-private",
        action="store_true",
        help="print prices and euro amounts even when personal values come from the environment",
    )
    args = parser.parse_args(argv)

    settings = config.with_env(config.load(args.config))
    private = config.uses_private_values() and not args.show_private
    tariff = tariffs.for_day(tariffs.load(args.tariffs), args.day)
    gas_price = args.gas_price or config.env_value(config.ENV_GAS_PRICE)
    electricity_price = args.electricity_price or config.env_value(config.ENV_ELECTRICITY_PRICE)
    if gas_price or electricity_price:
        prices = replace(
            tariff.prices,
            gas=gas_price or tariff.prices.gas,
            electricity=electricity_price or tariff.prices.electricity,
        )
        from_cli = args.gas_price or args.electricity_price
        source = "scenario from the command line" if from_cli else "your own prices (environment)"
        tariff = replace(tariff, prices=prices, source=source)

    if args.weather_json:
        temps = weather.parse(args.weather_json.read_text(encoding="utf-8"))
    else:
        try:
            temps = weather.fetch_daily_means(settings.latitude, settings.longitude)
        except OSError as e:
            # The error text can name the request, which holds the location.
            print(
                f"(no weather forecast: {e if not private else type(e).__name__})", file=sys.stderr
            )
            temps = {}
    write = private_report if private else report
    sys.stdout.write(write(settings, tariff, temps, args.day))
    return 0


if __name__ == "__main__":
    sys.exit(main())
