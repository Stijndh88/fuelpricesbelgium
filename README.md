# Fuel prices Belgium

Follow up and predict the official maximum fuel prices in Belgium, so you know
when it pays to wait (or hurry) to fill up.

## What is here

- `fuelprices fetch` downloads the official maximum prices published daily by FOD Economie
  and adds them to `data/max_prices.csv`.
- `fuelprices show` prints the latest known price per product.
- `python -m fuelprices.update` adds today's diesel and E10 max prices and the Brent crude price
  to `data/prices.sqlite`, one row per day. The "Daily price update" GitHub Action runs it every
  morning (and weekday afternoons) and commits the file. See [data/README.md](data/README.md).
- `fuelprices.rules` models when the government rules allow a price to go up or down.
  See [docs/price-rules.md](docs/price-rules.md) for sources and open questions.
- `python -m heating` compares heating the house with gas or with the heat pumps (airco units)
  and tells from which outdoor temperature on the heat pump is cheaper. Separate from the fuel
  price code; see [docs/heating.md](docs/heating.md).

## Getting started

```sh
python -m pip install -e '.[dev]'
pytest
ruff check . && ruff format --check .
fuelprices fetch            # needs access to economie.fgov.be
fuelprices fetch --html tests/fixtures/fod_sample.html   # offline, from a saved page
fuelprices show
```
