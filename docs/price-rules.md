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
  of the right shape. It has to be calibrated against the price history before predictions
  depend on it.
- **Moving average days.** Coded as the last 7 working days; it could be calendar days.
- **New base cost.** After a change the band is re-centred on that day's product cost; the
  annex may use the moving average instead.
- **Holidays.** Weekends are skipped; Belgian public holidays are not handled yet.
- **K-factor.** Energia mentions a damping factor in the formula; its effect is not modelled.
- **Crisis measures.** A 2026 bill (Kamer doc 56 1452) lets the government freeze maximum
  prices for up to 6 months, overriding these rules while it applies.
