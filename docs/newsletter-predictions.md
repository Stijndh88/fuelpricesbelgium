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

## Backfilled max prices

`python -m fuelprices.newsletter backfill` writes the max prices pinned down by the issues into
`data/prices.sqlite` for days that have none (189 days, 10 March to 7 October). A day is filled
when an issue states its price, or when two stated prices on either side are equal. When two
stated prices differ, the days in between stay empty because the day of the change is unknown:
14 diesel and 12 E10 days. Existing values (from the FOD page) are never overwritten.

Over this period diesel changed 32 times from one day to the next, a median of 6.2 cent/L and at
most 18.2; E10 changed 18 times, a median of 5.2 and at most 11.8. The smallest steps (0.7 to
1.0 cent/L on 1 July and 1 October, 1.4 on 7 May) are not market moves. Only changes between two
consecutive known days are counted, so changes next to a gap are missing.

## How accurate were the forecasts?

`python -m fuelprices.newsletter score` checks every forecast that was not already an announced
price: did the max price move in the forecast direction by the last forecast day, compared with
the price on the newsletter date? Forecasts without a day, or without a known price on both days,
are skipped (73 could be scored).

| | right | share |
|---|---|---|
| diesel, firm | 25 of 30 | 83% |
| E10, firm | 19 of 28 | 68% |
| all firm | 44 of 58 | 76% |
| all conditional ("if the product price holds") | 8 of 15 | 53% |

Every miss was a change that had not happened yet by the last forecast day (price unchanged),
none was in the wrong direction. Sizes are rarely given: for the 3 scored forecasts with a size
the average error was 3.9 cent/L. E10 forecasts miss more often than diesel, and conditional ones
are close to a coin flip.

The numbers were read out of the issues by hand (partly by parallel readers) and spot checks of
the whole file are advisable before a rule depends on one row. The issue dates use the header
inside the mail, which differs from the mail date in a few cases.
