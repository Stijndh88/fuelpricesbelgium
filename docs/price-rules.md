# How Belgian maximum fuel prices change

The rules are coded in `src/fuelprices/rules.py`. This page lists what each rule is based on
and what is still unconfirmed.

## Legal basis

Maximum prices are set under the programme contract (programma-overeenkomst) of 9 October 2006
between the Belgian State and the petroleum sector. The calculation is in article 13 of its
technical annex. That annex is not published online, so the exact percentages below come
from secondary sources.

## Confirmed

| Rule | Source |
|---|---|
| Max price = product cost + distribution margin + contributions (APETRA/Aseva, plus Promaz and the social heating fund for heating oil) + excise, with 21% VAT on the total | [Energia: achtergrondinformatie](https://www.energiafed.be/nl/maximumprijzen/achtergrondinformatie) |
| The product cost follows international quotations of finished products (Rotterdam, USD per tonne) and the EUR/USD rate | Energia; [La Libre](https://www.lalibre.be/economie/libre-entreprise/le-contrat-programme-ca-marche-comment-51b88bade4b0de6db9acb883) |
| FOD Economie computes a maximum price every working day; once a threshold is reached the new price applies the next day | Energia |
| Distribution margin is indexed on 1 April and 1 October (the +1 cent on 1 Oct 2026 in the Energieprijzen.vlaanderen newsletter) | Energia |
| Petrol, road diesel and LPG change only when the day's product cost **and** its 7-day moving average both leave a band around the cost the current price was based on | [Carbu.com barometer explanation](https://carbu.com/belgique/index.php/cif_detail?p=M&C=G) |
| The band narrows during the 7 days after a price change | Carbu.com |
| Heating oil and red diesel have had no threshold since mid-2018 and follow the product cost daily | [RTBF](https://www.rtbf.be/article/augmentation-des-prix-des-carburants-des-questions-que-vous-vous-posez-sur-la-fixation-de-ces-prix-11695587), [Landbouwleven](https://www.landbouwleven.be/13596/article/2022-04-23/belgie-kent-een-unieke-situatie-met-maximumprijzen-op-de-brandstoffenmarkt) |

## Not confirmed yet

- **Band widths.** `UNCONFIRMED_SCHEDULE` (3.0% narrowing to 1.5% over 7 days) is a placeholder
  of the right shape. `fuelprices calibrate` fits the widths to the real changes since 2019
  (see "Calibration results" below); the fit is not good enough yet to rely on.
- **Moving average days.** Coded as the last 7 working days; it could be calendar days.
- **New base cost.** After a change the band is re-centred on that day's product cost; the
  annex may use the moving average instead.
- **Holidays.** Weekends are skipped; Belgian public holidays are not handled yet.
- **K-factor.** Energia mentions a damping factor in the formula; its effect is not modelled.
- **Crisis measures.** A 2026 bill (Kamer doc 56 1452) lets the government freeze maximum
  prices for up to 6 months, overriding these rules while it applies.

## Calibration results (2026-10-06)

Daily maximum prices since 2011 come from petrolfed.be; the fit uses 2019 onwards (359 real
diesel changes, 277 for E10). The product cost is stood in for by the New York ULSD/RBOB future in
EUR/L, because the Rotterdam quotations are not free. `fuelprices calibrate` replays the rules with
band widths from a grid and scores them against the real changes, fitting on everything before the
last 180 days and testing on those 180 days.

What the history shows (solid):

- Changes take effect on Tuesday to Saturday (computed Monday to Friday) and never on Sunday.
- There is no fixed minimum gap: 1 to 45+ days between changes, a median around a week, about 50
  changes a year for diesel and 40 for E10.
- Typical step 3 cent/L (median), 5 cent/L (75th percentile), up to 30 cent/L in crises.

How well the replayed rules reproduce the real changes (the "exact day" figures need the right day
and direction; "within a day" allows one day off):

| | diesel B7 | E10 |
|---|---|---|
| Free-running replay, held-out half year: precision / recall | 65% / 39% | 41% / 27% |
| Replay restarted from every real change, exact day, precision / recall | about 40% / 40-60% | about 40% / 55% |
| Same, within a day, precision / recall | about 70% / 50-75% | about 70% / 60% |

Conclusion: the rules with these band widths and the stand-in cost explain roughly half of the real
changes and about a third of the changes they predict do not happen on that day. That is below the
bar for the advice (precision and recall of at least 70% on days the fit never saw), so predictions
beyond tomorrow's published price stay labelled as a guess. The most likely reasons: the stand-in
cost differs from the Rotterdam quotations, the unpublished damping (K) factor, and the real band
widths. A better fit needs the Rotterdam product quotations (for example from the monthly
newsletter figures) or the technical annex.

### Rotterdam product prices from the newsletter (2026-10-06)

The newsletter quotes the wholesale product price in EUR per 1000 L, but only in 20 of its 119
issues (22 June to 5 October, 18 for diesel and 14 for E10), so it is too sparse to refit the
rules on: that covers about eight real diesel changes. It does show how good the stand-in is
(`fuelprices calibrate` prints this):

| | quotes | correlation with the stand-in | newsletter minus stand-in |
|---|---|---|---|
| diesel | 18 | 0.98 | +37 EUR/1000 L on average, spread 31 |
| E10 | 14 | 0.2 | +60 EUR/1000 L on average, spread 44 |

- Diesel: the New York ULSD future follows the quoted price closely, but the spread of about 31
  EUR/1000 L (3 cent/L before VAT, around 3% of the cost) is as large as the band itself (1.5% to
  3%). Day to day the stand-in is too noisy to tell whether the real band was left, which explains
  the ~65% precision and ~40% recall. A daily series of the real quotation would remove this.
- E10: the RBOB future does not track the quoted petrol price at all in this period (correlation
  0.2), so the E10 fit cannot get good with this stand-in. Belgian petrol follows the Eurobob
  quotation, which is a different contract.

Conclusion: the fit does not reach the 70% bar and cannot with these inputs; predictions beyond
tomorrow's published price stay a guess. Collecting the newsletter's product price on every issue
(it appears about twice a week) would slowly build the missing series.

### The official gasoil cost: heating oil max price (2026-10-06)

Searched for a free daily Rotterdam gasoil quotation: Platts (the quotation the formula uses) is a
paid subscription; ICE settlements and Eurobob need a data licence (the free delayed-data
endpoints answer 403); Yahoo Finance has no ICE gasoil or Eurobob symbol; the EU Weekly Oil
Bulletin is weekly and holds consumer prices; FOD Economie, Energia and carbu.com only publish the
resulting max prices. What is public and official is the max price of heating oil
(H0/H7, 2000 L and up): it has no band since 2018 and follows the same gasoil cost every day. The
daily series (petrolfed.be, same export as the diesel max price, 2011 onwards) is the gasoil cost
the Belgian formula produced, up to a constant (margin, duties, contributions).

Checks on that series:

- It changes on 251 of about 260 working days a year, never on Sunday, with the same big moves as
  diesel (for example 10 April 2026, -26 cent/L both).
- The price valid on day D+1 is computed on day D. The New York diesel future follows it with
  one more day of delay: daily changes correlate 0.71 at that lag and about 0.05 without.
- On the 345 real diesel changes since mid-2019, the diesel step divided by the move of the
  heating oil cost since the previous change has median 0.97 (middle half 0.87 to 1.12). So a
  diesel change passes on about 100% of the cost move measured on the day it happens, not on a
  7-day average (that ratio scatters from -3 to 4). The expected size of a change is reliable.

Fit of the band rules on diesel with this cost (fit on everything before the last 180 days,
tested on those 180 days, 38 real changes):

| | precision | recall |
|---|---|---|
| New York stand-in (before) | 65% | 39% |
| official gasoil cost, free-running replay | 73% | 63% |
| official gasoil cost, restarted from each real change | 75-78% | 55-79% |

Direction is right in 98% of the changes that happen, and precision now clears 70%, but recall
does not, and on the fit period (2019 to April 2026, 315 changes) precision is only about 50%.
So the model still misses part of the real mechanism (the unpublished annex: exact band widths,
how the moving average enters, minimum days between changes). Diesel predictions beyond tomorrow's
published price therefore stay a guess, a much better informed one. E10 has no such series: petrol
has no band-free sibling, so it stays on the RBOB stand-in (correlation 0.2 with the quoted
price) and stays a guess.
