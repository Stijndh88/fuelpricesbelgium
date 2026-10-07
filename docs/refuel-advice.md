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
   that rough expected change; inside it gives no difference. For diesel, when the stored history
   has the official daily gasoil cost (the heating oil max price, known the same morning for
   today), that cost replaces Brent here: its move since the cost behind the last diesel change is
   compared with the band. Brent is only the fallback.
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
- The band widths are fitted to the real price history but the fit is not good enough yet
  (about half of the real changes are reproduced; see [price-rules.md](price-rules.md)). Until a fit
  scores at least 70% precision and recall on days it was not fitted on, every prediction beyond
  tomorrow's published price has `is_guess: true` and says "(a guess)". The fit is re-run daily and
  written to `data/calibration.json`; `advice.json` carries a `calibration` block per product.
- Brent and the diesel/gasoline shock flag use a fixed EUR/USD rate of 1.10.
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

## Notifications

The daily workflow can push the advice to a [ntfy](https://ntfy.sh) topic; anyone subscribes in
the ntfy app or on ntfy.sh with the topic name, no account needed. Set the repository secret
`NTFY_TOPIC` to a long random name (the repo is public, so keep it secret). Without it the step
is skipped. A message goes out only when the action for diesel B7 or E10 changed; set the
repository variable `NTFY_DAILY` to `1` for a summary every run. Try it locally with
`python -m fuelprices.notify --dry-run`.

## Languages

Every text in `advice.json` comes as an English sentence plus a stable message code and parameters
(`reason_code`/`reason_params`, `market_note_params`, `caveat_codes`; the headline follows from
`action`). The dashboard renders them in Dutch or English from its own table in `site/i18n.js`
and never shows the English sentence on the Dutch page: for a code it does not know it shows a
Dutch notice to reload (the English page may fall back to the English sentence). Rule: every
user-facing Dutch text must be Dutch; `tests/test_messages.py` scans the Dutch templates and the
Dutch dashboard table for English words, so a new text without a proper Dutch version fails CI. The templates live in
`src/fuelprices/messages.py`; a test checks both tables hold the same codes. The ntfy message is
Dutch only; set the repository variable `NTFY_LANGUAGES` (`en`, `nl` or `nl,en`) to change that.
