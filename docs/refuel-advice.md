# Refuel advice

`fuelprices advise` (and `data/advice.json`, written by the daily job) gives one call per product,
diesel B7 and E10: **fill up today**, **wait** or **no difference**, with a one-line reason and the
expected change of the maximum price in cent/L. The code is in `src/fuelprices/advice.py`.

## How it decides

1. **Tomorrow's price is published.** FOD Economie publishes the next day's maximum price on
   working-day afternoons. A drop of at least 0.5 cent/L means wait, a rise means fill up today,
   anything smaller means no difference. This part is certain.
2. **Not published yet (or unchanged).** Brent crude is compared with its level just before the
   last price change. The move is converted to EUR/L (fixed rate 1.10 USD/EUR, 159 L per barrel,
   21% VAT on top) and compared with the band of the price rules (`fuelprices.rules`) at the next
   day a change could apply. Outside the band in either direction gives wait or fill up today with
   that rough expected change; inside it gives no difference.
3. **Market shock** (checked before step 2). If Brent or the matching product future moved at
   least 5% over 5 days (`--shock-threshold`, default 0.05; 0 turns it off), the advice is fill up
   today for a rise and wait for a drop, even when the rules band is not reached yet. Max prices
   follow wholesale prices with a lag of a few days under the price rules, so a market move today
   shows up in the max price soon after. Diesel looks at NYMEX ULSD (`HO=F`), E10 at NYMEX RBOB
   (`RB=F`), both with Brent. Big moves in opposite directions cancel out. A big move also shows as
   `market_note` when the published price already decides. News is not read: a shock in the news
   reaches these prices within minutes.
4. **Nothing to go on** (no price today, no recent Brent): no difference, and the reason says why.

The next day a change could apply skips the weekend: a price computed on Friday applies on
Saturday, and the next one is computed on Monday and applies on Tuesday.

## What it cannot know

- The European diesel benchmark, ICE low-sulphur gasoil, has no free daily source that works
  without a key (not on Yahoo Finance; FRED blocks GitHub Actions, and EIA needs a key).
  The New York ULSD and RBOB futures trade in the same market and serve as stand-ins.
- The wholesale diesel and petrol quotations (Platts Rotterdam) that actually trigger a change are
  not free. Brent is only a stand-in: the refining margin can move on its own, as it did for
  diesel in the 2 October 2026 newsletter ("narrowly escaped an increase").
- The band widths are placeholders until calibrated (see [price-rules.md](price-rules.md)).
- The EUR/USD rate is fixed at 1.10.
- Belgian public holidays, government price freezes and pump prices below the maximum.

## Backtest

`backtest()` replays the advice over the stored history. For every start day with seven days of
known prices, you need fuel within those seven days: following the advice means filling up on the
first day it does not say wait (or on the last day). The baseline is a random day in the window,
whose expected price is the window's average. It reports how many windows the advice saved at
least 0.1 cent/L, made no difference, or cost money, and the average saving. It runs once with
the shock flag off and once at the configured threshold, so the JSON shows whether the flag
helps; try other thresholds with `fuelprices advise --shock-threshold 0.03`. The history only
started on 7 October 2026, so it reports "not enough history" until a week of prices is stored.
