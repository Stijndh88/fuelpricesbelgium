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

## What you need to fill in

- Your supplier's all-in variable price for gas and electricity each month
  (`data/heating_tariffs.csv`). If you have a fixed-price contract, one row is enough.
- Your annual gas use in kWh from the yearly bill, and the boiler type (condensing or not).
- Your airco units' COP at a few outdoor temperatures (datasheet, EN 14511: usually +7, +2,
  -7 °C) or at least the SCOP, and your location.

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
