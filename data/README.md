# Price history

`prices.sqlite` holds one row per day in the table `daily_prices`, updated each
morning by the "Daily price update" GitHub Action (`python -m fuelprices.update`).

| column | meaning | unit | source |
|---|---|---|---|
| `day` | date the prices are valid on | ISO date | |
| `diesel_max` | official maximum price, diesel B7 | EUR/L incl. VAT | FOD Economie |
| `e10_max` | official maximum price, petrol E10 (95) | EUR/L incl. VAT | FOD Economie |
| `diesel_product` | wholesale product cost, diesel | EUR/L (as used by `fuelprices.rules`) | not sourced yet |
| `e10_product` | wholesale product cost, petrol | EUR/L (as used by `fuelprices.rules`) | not sourced yet |
| `brent_usd` | Brent crude, front-month ICE future daily close | USD per barrel | Yahoo Finance `BZ=F` (unofficial endpoint) |
| `ulsd_usd_gal` | NYMEX ULSD (New York Harbor diesel) future, front month, daily close | USD per gallon | Yahoo Finance `HO=F` (unofficial endpoint) |
| `rbob_usd_gal` | NYMEX RBOB gasoline future, front month, daily close | USD per gallon | Yahoo Finance `RB=F` (unofficial endpoint) |
| `updated_at` | last time a value in the row changed | UTC timestamp | |

Max prices stay in force until a new one is published, so days without a publication
(weekends, a missed run) carry the previous day's price. Empty cells are values not (yet)
available. A rerun never overwrites a known value
with an empty one, and leaves the file unchanged when nothing new came in.

Query it with `sqlite3 data/prices.sqlite "select * from daily_prices order by day"`.

The first daily run was on 6 October 2026, after FOD Economie had already switched its page to
the tariff valid from 7 October, so the price in force on 6 October was never fetched. Diesel
2.432 EUR/L for that day was entered by hand (told by Stijn); E10 for that day is unknown.

## Newsletter facts

`newsletter_predictions.csv` holds the max prices, product prices, crude price and forecasts
stated in the Energieprijzen.vlaanderen newsletter (only numbers). Its columns and how well the
forecasts did are in [../docs/newsletter-predictions.md](../docs/newsletter-predictions.md).
The max prices it pins down were backfilled into `prices.sqlite` for 10 March to 5 October 2026.
