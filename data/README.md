# Price history

`prices.sqlite` holds one row per day in the table `daily_prices`, updated each
morning by the "Daily price update" GitHub Action (`python -m fuelprices.update`).

| column | meaning | unit | source |
|---|---|---|---|
| `day` | date the prices are valid on | ISO date | |
| `diesel_max` | official maximum price, diesel B7 | EUR/L incl. VAT | FOD Economie |
| `e10_max` | official maximum price, petrol E10 (95) | EUR/L incl. VAT | FOD Economie |
| `diesel_product` | wholesale product price, diesel | EUR per 1000 L | not sourced yet |
| `e10_product` | wholesale product price, petrol | EUR per 1000 L | not sourced yet |
| `brent_usd` | Brent crude spot | USD per barrel | FRED `DCOILBRENTEU` (EIA), lags a few working days |
| `updated_at` | last time a value in the row changed | UTC timestamp | |

Max prices stay in force until a new one is published, so days without a publication
(weekends, a missed run) carry the previous day's price. Empty cells are values not (yet)
available. A rerun never overwrites a known value
with an empty one, and leaves the file unchanged when nothing new came in.

Query it with `sqlite3 data/prices.sqlite "select * from daily_prices order by day"`.
