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
