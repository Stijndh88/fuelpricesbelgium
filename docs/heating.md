# Heating: gas or heat pump

`python -m heating` compares heating the house with the gas boiler and with the heat pumps
(airco units), today and for the coming week, and says from which outdoor temperature on the
heat pump is the cheaper one. It is separate from the car fuel code (`src/heating/`).

## How it works

- Heat from gas costs `gas price / boiler efficiency` per kWh (efficiency ~0.9 for a condensing
  boiler). Heat from the heat pump costs `electricity price / COP`.
- The heat pump is cheaper whenever `COP > electricity price × efficiency / gas price`
  (the break-even COP). With September 2026 Flemish averages (gas 0.105, electricity 0.31
  EUR/kWh all-in) that is a COP of about 2.7.
- An air-to-air unit's COP falls as it gets colder, so the break-even COP becomes a switch
  temperature: above it use the heat pump, below it use gas. The COP curve is in
  `config/heating.toml`.
- How much heat the house needs per day comes from the degree-day method, scaled so a normal
  year matches your annual gas use on the bill.
- The "Heating advice" GitHub Action runs each morning from October to April and writes the
  report to the run's summary page.

## The airco units

Each outdoor unit is listed with its rated heating power at +7 °C and at -10 °C and its SCOP.
- **COP curve:** a generic COP-by-temperature curve is scaled so that, over the EN 14825
  average heating season, it gives the units' combined SCOP (4.41 for the AJ040 plus AJ068).
  This is an estimate of the shape; datasheet COP values at several temperatures would be better.
- **Capacity:** the available heating power falls linearly from the +7 °C rating to the -10 °C
  rating (12.2 kW to 7.8 kW for both outdoor units together). On a day when the house needs more
  heat than that, the model lets gas cover the rest and the report shows the share the heat
  pumps deliver. The model counts the rated power for the whole outdoor unit; in practice each
  indoor unit only heats its own room.

## Data sources

| what | source | status |
|---|---|---|
| Outdoor temperature (past week + 7-day forecast) | Open-Meteo forecast API, free, no key | used; blocked from the Claude cloud container, works from GitHub Actions |
| All-in gas and electricity price per kWh | `data/heating_tariffs.csv`, one row per month | filled in by hand from the supplier's monthly tariff card; seeded with Test Aankoop's Flemish averages for September 2026 |
| Belgian day-ahead electricity (EPEX BE) | energy-charts.info API, free, no key | reachable, not used yet: only matters for a dynamic contract |
| TTF gas (drives variable gas prices, TTF 101) | no free daily feed confirmed; BFE (Swiss) open data has an indexed TTF front-month series but it looked stale | not used |
| CREG, VREG V-test, Synergrid, supplier sites | | blocked from the Claude cloud container; not checked |

Why the tariff is entered by hand: variable contracts change once a month, and the all-in
price (energy plus network costs, levies and VAT) differs per supplier and region, so your own
tariff card is the only exact source.

## Keeping your own values private

The repository is public, so your address, tariffs and gas use do not go in it. The files in
the repo only hold generic defaults and the airco datasheets. Your own values are read from
environment variables, which in GitHub Actions are **repository secrets**
(Settings > Secrets and variables > Actions > Secrets; secrets, unlike variables, are masked
in logs). Any that is unset or empty falls back to the default.

| secret | what | default |
|---|---|---|
| `HEATING_LATITUDE`, `HEATING_LONGITUDE` | where you live, for the weather | Brussels |
| `HEATING_GAS_EUR_PER_KWH` | all-in gas price | `data/heating_tariffs.csv` |
| `HEATING_ELECTRICITY_EUR_PER_KWH` | all-in electricity price | `data/heating_tariffs.csv` |
| `HEATING_ANNUAL_GAS_KWH` | yearly gas use from the bill | 17000 |
| `HEATING_BOILER_EFFICIENCY` | e.g. 0.9 (0,9 also works) | 0.9 |
| `HEATING_HOT_WATER_SHARE` | optional, share of gas used for hot water | 0.15 |

When any of them is set, the report on the Action's summary page (visible to everyone) shows
only the verdict: the switch temperature and which option is cheaper each day. It leaves out
prices, gas use, boiler, location, kWh and euro amounts, and the break-even COP, which would
reveal the price ratio. To see the full report, run it on your own machine with the values in
your shell and `--show-private`:

```sh
HEATING_GAS_EUR_PER_KWH=0.11 HEATING_ELECTRICITY_EUR_PER_KWH=0.30 python -m heating --show-private
```

## What you need to fill in

- Your supplier's all-in variable price for gas and electricity each month, as secrets (above);
  update them when your tariff card changes.
- Your annual gas use in kWh from the yearly bill, and the boiler type (condensing or not).
- Your location, for the weather. The airco units are already in `config/heating.toml`
  (Samsung AJ040 and AJ068, from the datasheets). Measured COP values at a few outdoor
  temperatures would replace the SCOP-based estimate below.

## Limits

- Split airco units usually heat one room each; if they can't heat the whole house, the real
  answer is a mix. The model assumes they can.
- In Flanders the capacity tariff charges for your monthly peak (kW). Running several units at
  once can raise it; that cost is not in the model yet.
- The COP is taken at the daily mean temperature; nights are colder, so the heat pump
  does slightly worse than shown on days near the switch temperature.
- From 1 August 2026 excise on gas rises and on electricity falls in steps to 2029; from
  2028 Flanders moves levies from electricity to gas. Both push the switch temperature down.
  Enter new tariffs as they come.
