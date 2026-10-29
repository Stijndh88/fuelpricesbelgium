# E5 tegenover E10: bewegen ze hetzelfde?

Rapport van 29 oktober 2026, op basis van de maximumprijzen in `data/prices.sqlite`. E5 95 komt
uit de petrolfed-export (vanaf 1 oktober), E5 98 van de FOD-pagina (vanaf 16 oktober).

## Wijzigingen naast elkaar (cent/L, plus is een stijging)

| Dag | E10 | E5 95 | E5 98 | Verschil E5 95 met E10 | Verschil E5 98 met E10 |
|---|---|---|---|---|---|
| 2 okt | +4,4 | +5,0 | niet bewaard | +0,6 | |
| 13 okt | +4,0 | +3,6 | niet bewaard | -0,4 | |
| 15 okt | -4,1 | -3,4 | niet bewaard | +0,7 | |
| 21 okt | -6,2 | -6,4 | -3,8 | -0,2 | +2,4 |
| 28 okt | -1,4 | -3,6 | -1,4 | -2,2 | 0,0 |

(1 oktober: E10 +1,0; E5 95 had toen nog geen vorige waarde in onze opslag.)

## Het verschil in prijs (E5 min E10)

- E5 95 ligt 3,3 tot 5,7 cent/L boven E10. Het verschil bleef rond 5 cent, maar daalde op 28 okt
  naar 3,3 omdat E5 95 toen meer daalde dan E10.
- E5 98 ligt 13,7 tot 16,1 cent/L boven E10 (16 okt: 13,7; 21 en 28 okt: 16,1). Op 7 okt was het
  nog 19,4, dus ook dat verschil schuift mee.

## Wat dat betekent

- **Dag en richting: telkens gelijk.** In de 5 wijzigingen waar we E5 en E10 allebei zien, gebeurden
  ze op dezelfde dag en in dezelfde richting. E5 98 ken ik maar in 2 wijzigingen, ook daar
  dezelfde dag en richting.
- **Grootte: verschilt tot 2,4 cent/L** (E5 95 tot 2,2, E5 98 tot 2,4). Vermoedelijk heeft E5
  een eigen aandeel in de berekening, maar dat kunnen we met zo weinig wijzigingen niet vastleggen.
- Dat zijn maar 5 wijzigingen (E5 98: 2). Dit is een eerste indruk, geen bewijs.

## Conclusie

Een apart E5-advies zegt bijna altijd hetzelfde als het E10-advies: "wacht" of "tank vandaag" op
dezelfde dag. Wat een E5-advies zou toevoegen is alleen de grootte van de wijziging, en die kunnen
we voor E10 zelf al niet goed voorspellen. Mijn advies: **geen apart E5-advies bouwen.** Wil je
toch iets, dan kan het dashboard bij E10 een korte regel tonen ("E5 volgt meestal op dezelfde dag,
de grootte kan 2 cent/L afwijken"). De gegevens blijven dagelijks opgeslagen, zodat we dit over een
paar maanden met meer wijzigingen opnieuw kunnen nakijken.
