# Newsletter predictions

`data/newsletter_predictions.csv` holds the numbers stated in the Energieprijzen.vlaanderen
newsletter, one row per issue: 119 issues from 8 March to 6 October 2026. Only numbers are
stored, never newsletter text. Older mails (2019 to 2024, 15 of them) state no prices and were
left out.

| column | meaning |
|---|---|
| `date` | newsletter date |
| `diesel_now`, `e10_now` | official max price valid that day, EUR/L (empty when the issue does not state it) |
| `diesel_next`, `e10_next`, `next_effective` | the already published next max price and the day it starts |
| `diesel_pred_dir`, `e10_pred_dir` | forecast of a further change: `up`, `down`, `flat`, or `up_conditional` / `down_conditional` when it depends on the product price holding or moving |
| `*_pred_ct` | forecast size in cent/L when the issue states one (a range is `7-9`); most issues give a target price or no size, so this is mostly empty |
| `*_pred_day` | day or days the change is expected, `a/b` for "a or b" |
| `diesel_product_eur_per_1000l`, `e10_product_eur_per_1000l` | wholesale product price, EUR per 1000 L, only from 8 September on (earlier issues quote nothing or a different unit) |
| `crude_usd` | crude oil price in USD as rounded in the issue |

The product prices are the author's own quotes and have not been checked against the
quotation `fuelprices.rules` expects, so they are not in `data/prices.sqlite`.

## Checked against the official history

The max prices stated in the issues were compared with `data/prices.sqlite` (the official
history, backfilled from petrolfed.be): of about 1,000 stated prices, 12 differ, mostly by 0.2 to
0.3 cent/L, in March, May, June and July (the largest, E10 on 24 to 30 July, is 2.0 cent/L). The
list is `python -m fuelprices.newsletter check`. Treat the stated prices as estimates and the
history as the truth; the product and crude columns have no second source.

## How accurate were the forecasts?

`python -m fuelprices.newsletter score` checks every forecast that was not already an announced
price: did the official max price move in the forecast direction by the last forecast day,
compared with the price on the newsletter date? Forecasts without a day are skipped (90 could be
scored).

| | right | share |
|---|---|---|
| diesel, firm | 29 of 34 | 85% |
| E10, firm | 29 of 38 | 76% |
| all firm | 58 of 72 | 81% |
| all conditional ("if the product price holds") | 10 of 18 | 56% |

Every miss was a change that had not happened yet by the last forecast day (price unchanged),
none was in the wrong direction, so the direction is reliable and the timing is the weak point.
Sizes are rarely given: for the 6 correct forecasts with a size the average error was 2.6
cent/L. E10 forecasts miss more often than diesel, and conditional ones are close to a coin flip.

The numbers were read out of the issues by hand (partly by parallel readers) and spot checks of
the whole file are advisable before a rule depends on one row. The issue dates use the header
inside the mail, which differs from the mail date in a few cases.
