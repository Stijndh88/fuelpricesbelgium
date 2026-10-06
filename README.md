# Fuel prices Belgium

Follow up and predict the official maximum fuel prices in Belgium, so you know
when it pays to wait (or hurry) to fill up.

## What is here

- `fuelprices fetch` downloads the official maximum prices published daily by FOD Economie
  and adds them to `data/max_prices.csv`.
- `fuelprices show` prints the latest known price per product.
- `fuelprices.rules` models when the government rules allow a price to go up or down.
  See [docs/price-rules.md](docs/price-rules.md) for sources and open questions.

## Getting started

```sh
python -m pip install -e '.[dev]'
pytest
ruff check . && ruff format --check .
fuelprices fetch            # needs access to petrolprices.economie.fgov.be
fuelprices fetch --html tests/fixtures/petrolprices_nl.html   # offline, from a saved page
fuelprices show
```
