"""Advice texts as message codes with parameters, in English and Dutch (Belgian).

``advice.json`` carries the code and parameters next to the English sentence, so the dashboard and
the notifications can show the text in the reader's language. The dashboard keeps its own copy of
the templates in ``site/i18n.js``; the codes here and there must stay in step.

Parameters: ``day``/``when``/``since`` are ISO dates, ``today``/``tomorrow`` are prices in EUR/L,
``cents`` is cent/L, ``pct`` is a percentage and ``name`` is the market series name.
"""

from __future__ import annotations

from datetime import date

LANGUAGES = ("nl", "en")

HEADLINES = {
    "en": {"wait": "Wait", "fill_up_today": "Fill up today", "no_difference": "No difference"},
    "nl": {"wait": "Wacht", "fill_up_today": "Tank vandaag", "no_difference": "Geen verschil"},
}

MARKET_NAMES = {
    "en": {
        "Diesel futures": "Diesel futures",
        "Gasoline futures": "Gasoline futures",
        "Brent": "Brent",
    },
    "nl": {
        "Diesel futures": "Diesel-futures",
        "Gasoline futures": "Benzine-futures",
        "Brent": "Brent",
    },
}

WEEKDAYS = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "nl": ("ma", "di", "wo", "do", "vr", "za", "zo"),
}

MARKET_NOTE = {
    "en": "Big market move: {name} {pct} since {since}.",
    "nl": "Grote marktbeweging: {name} {pct} sinds {since}.",
}

REASONS = {
    "en": {
        "no_price_today": "No maximum price known for today.",
        "tomorrow_only": "Tomorrow's maximum price is published ({tomorrow}), but today's is not "
        "stored yet, so the two cannot be compared.",
        "wait_published": "Wait until tomorrow ({day}): the maximum price drops {cents} cent/L, "
        "{today} to {tomorrow} (published).",
        "fill_published": "Fill up today: the maximum price rises {cents} cent/L tomorrow ({day}), "
        "{today} to {tomorrow} (published).",
        "small_change": "Tomorrow's price differs by only {cents} cent/L (published).",
        "shock_wait": "{name} {pct} since {since}: a drop is likely from {when} or soon after.",
        "shock_fill": "{name} {pct} since {since}: a rise is likely from {when} or soon after.",
        "brent_no_data": "No recent Brent price and no published change for tomorrow.",
        "brent_no_base": "No Brent price from around the last price change.",
        "brent_inside_band": "Brent {brent_from} to {brent_to} USD since {since}: inside the band, "
        "no change expected by {when}.",
        "brent_wait": "Brent {brent_from} to {brent_to} USD since {since}: a drop is likely "
        "from {when}.",
        "brent_fill": "Brent {brent_from} to {brent_to} USD since {since}: a rise is likely "
        "from {when}.",
        "brent_wait_guess": "Brent {brent_from} to {brent_to} USD since {since}: a drop is "
        "possible from {when} (a guess).",
        "brent_fill_guess": "Brent {brent_from} to {brent_to} USD since {since}: a rise is "
        "possible from {when} (a guess).",
        "gasoil_inside_band": "Wholesale gasoil price (via the heating oil max price) {cost_from} to "
        "{cost_to} EUR/L since {since}: inside the band, no change expected by {when}.",
        "gasoil_wait": "Wholesale gasoil price (via the heating oil max price) {cost_from} to {cost_to} "
        "EUR/L since {since}: a drop is likely from {when}.",
        "gasoil_fill": "Wholesale gasoil price (via the heating oil max price) {cost_from} to {cost_to} "
        "EUR/L since {since}: a rise is likely from {when}.",
        "gasoil_wait_guess": "Wholesale gasoil price (via the heating oil max price) {cost_from} to "
        "{cost_to} EUR/L since {since}: a drop is possible from {when} (a guess).",
        "gasoil_fill_guess": "Wholesale gasoil price (via the heating oil max price) {cost_from} to "
        "{cost_to} EUR/L since {since}: a rise is possible from {when} (a guess).",
    },
    "nl": {
        "no_price_today": "Geen maximumprijs bekend voor vandaag.",
        "tomorrow_only": "De maximumprijs van morgen is gepubliceerd ({tomorrow}), maar die van "
        "vandaag is nog niet opgeslagen, dus ze kunnen niet vergeleken worden.",
        "wait_published": "Wacht tot morgen ({day}): de maximumprijs daalt {cents} cent/L, van "
        "{today} naar {tomorrow} (gepubliceerd).",
        "fill_published": "Tank vandaag: de maximumprijs stijgt morgen ({day}) met {cents} cent/L, "
        "van {today} naar {tomorrow} (gepubliceerd).",
        "small_change": "De prijs van morgen verschilt maar {cents} cent/L (gepubliceerd).",
        "shock_wait": "{name} {pct} sinds {since}: een daling is waarschijnlijk vanaf {when} of "
        "kort daarna.",
        "shock_fill": "{name} {pct} sinds {since}: een stijging is waarschijnlijk vanaf {when} of "
        "kort daarna.",
        "brent_no_data": "Geen recente Brent-prijs en geen gepubliceerde wijziging voor morgen.",
        "brent_no_base": "Geen Brent-prijs rond de laatste prijswijziging.",
        "brent_inside_band": "Brent van {brent_from} naar {brent_to} USD sinds {since}: binnen de "
        "band, geen wijziging verwacht tegen {when}.",
        "brent_wait": "Brent van {brent_from} naar {brent_to} USD sinds {since}: een daling is "
        "waarschijnlijk vanaf {when}.",
        "brent_fill": "Brent van {brent_from} naar {brent_to} USD sinds {since}: een stijging is "
        "waarschijnlijk vanaf {when}.",
        "brent_wait_guess": "Brent van {brent_from} naar {brent_to} USD sinds {since}: een daling "
        "is mogelijk vanaf {when} (een gok).",
        "brent_fill_guess": "Brent van {brent_from} naar {brent_to} USD sinds {since}: een "
        "stijging is mogelijk vanaf {when} (een gok).",
        "gasoil_inside_band": "Groothandelsprijs gasolie (via maximumprijs stookolie) van {cost_from} naar "
        "{cost_to} EUR/L sinds {since}: binnen de band, geen wijziging verwacht tegen {when}.",
        "gasoil_wait": "Groothandelsprijs gasolie (via maximumprijs stookolie) van {cost_from} naar "
        "{cost_to} EUR/L sinds {since}: een daling is waarschijnlijk vanaf {when}.",
        "gasoil_fill": "Groothandelsprijs gasolie (via maximumprijs stookolie) van {cost_from} naar "
        "{cost_to} EUR/L sinds {since}: een stijging is waarschijnlijk vanaf {when}.",
        "gasoil_wait_guess": "Groothandelsprijs gasolie (via maximumprijs stookolie) van {cost_from} naar "
        "{cost_to} EUR/L sinds {since}: een daling is mogelijk vanaf {when} (een gok).",
        "gasoil_fill_guess": "Groothandelsprijs gasolie (via maximumprijs stookolie) van {cost_from} naar "
        "{cost_to} EUR/L sinds {since}: een stijging is mogelijk vanaf {when} (een gok).",
    },
}

CAVEATS = {
    "wholesale_proxy": {
        "en": "The wholesale diesel and petrol quotations that actually trigger a change are not "
        "free, so beyond tomorrow's published price the advice uses Brent crude as a rough "
        "stand-in.",
        "nl": "De groothandelsnoteringen voor diesel en benzine die een prijswijziging echt "
        "aansturen zijn niet gratis, dus buiten de gepubliceerde prijs van morgen gebruikt het "
        "advies ruwe olie (Brent) als grove benadering.",
    },
    "bands_fit": {
        "en": "The exact band widths of the price rules are not public. They are fitted to the "
        "real price history; until the fit reproduces the real "
        "changes well enough on days it was not fitted on, predictions beyond tomorrow's "
        "published price are labelled a guess.",
        "nl": "De exacte breedtes van de prijsbanden uit de regels zijn niet openbaar. Ze worden "
        "gefit op de echte prijshistoriek; zolang de fit de echte "
        "wijzigingen op niet-gefitte dagen niet goed genoeg nabootst, zijn voorspellingen buiten "
        "de gepubliceerde prijs van morgen een gok.",
    },
    "fx_fixed": {
        "en": "Brent and US futures are converted at a fixed EUR/USD rate. The diesel and "
        "gasoline futures are New York contracts, a stand-in for the Rotterdam quotations "
        "Belgium uses.",
        "nl": "Brent en Amerikaanse futures worden omgerekend tegen een vaste EUR/USD-koers. De "
        "diesel- en benzinefutures zijn New Yorkse contracten, een benadering van de Rotterdamse "
        "noteringen die België gebruikt.",
    },
    "shock_prices_only": {
        "en": "The market shock flag looks at prices, not news: news only counts once markets "
        "move.",
        "nl": "De marktschokvlag kijkt naar prijzen, niet naar nieuws: nieuws telt pas mee zodra "
        "de markten bewegen.",
    },
    "holidays_ignored": {
        "en": "Belgian public holidays and government price freezes are not taken into account.",
        "nl": "Belgische feestdagen en prijsbevriezingen door de overheid worden niet meegerekend.",
    },
    "pump_below_max": {
        "en": "Pump prices can be below the official maximum; the advice is about the maximum "
        "price.",
        "nl": "De pompprijs kan lager zijn dan de officiële maximumprijs; het advies gaat over de "
        "maximumprijs.",
    },
}


def _day(lang: str, iso: str, with_weekday: bool) -> str:
    d = date.fromisoformat(iso)
    text = f"{d:%d/%m}"
    return f"{WEEKDAYS[lang][d.weekday()]} {text}" if with_weekday else text


def _fill(lang: str, params: dict) -> dict:
    out = {}
    for key, value in params.items():
        if key in ("day", "when"):
            out[key] = _day(lang, value, True)
        elif key == "since":
            out[key] = _day(lang, value, False)
        elif key == "pct":
            out[key] = f"{value:+.1f}%"
        elif key == "name":
            out[key] = MARKET_NAMES[lang].get(value, value)
        elif key in ("today", "tomorrow"):
            out[key] = f"{value:.3f}"
        elif key == "cents":
            out[key] = f"{value:.1f}"
        elif key in ("brent_from", "brent_to"):
            out[key] = f"{value:.0f}"
        else:
            out[key] = value
    return out


def reason(code: str, params: dict | None = None, lang: str = "en") -> str:
    return REASONS[lang][code].format(**_fill(lang, params or {}))


def market_note(params: dict, lang: str = "en") -> str:
    return MARKET_NOTE[lang].format(**_fill(lang, params))


def caveat(code: str, lang: str = "en") -> str:
    return CAVEATS[code][lang]


def headline(action: str, lang: str = "en") -> str:
    return HEADLINES[lang][action]
