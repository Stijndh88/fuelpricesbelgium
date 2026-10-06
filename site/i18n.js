"use strict";

// All page text in one place. Add a language by adding a table here and a button in the header.
// {placeholders} are filled by t(); the advice texts are rendered from the codes and parameters
// in advice.json (reason_code, market_note_params, caveat_codes) and fall back to the English
// strings that file also carries when a code is unknown.

const LANGS = { nl: "nl-BE", en: "en-GB" };

const I18N = {
  en: {
    title: "Fuel prices Belgium",
    description:
      "Official maximum prices for diesel B7 and petrol E10 in Belgium, with tomorrow's price and refuel advice.",
    loading: "Loading prices…",
    updated: "Official maximum prices, updated {stamp}.",
    load_error: "Could not load the prices. Try again later.",
    language: "Language",
    advice_title: "Refuel advice",
    advice_placeholder:
      "Advice is not available yet. It will appear here once the daily job starts publishing it.",
    advice_for: "Advice for {day}",
    diesel: "Diesel B7",
    e10: "Petrol E10",
    today: "Today",
    tomorrow: "Tomorrow",
    no_price_yet: "No price yet",
    since: "since {day}",
    not_published: "Not published yet. FOD Economie announces changes on working days, in the afternoon.",
    unchanged: "= unchanged",
    up: "▲ up {cents} cent",
    down: "▼ down {cents} cent",
    per_litre: " /L",
    history_title: "Maximum price, EUR per litre",
    brent_title: "Brent crude, USD per barrel",
    range: "Time range",
    d30: "30d",
    d90: "90d",
    d365: "1y",
    dall: "All",
    chart_empty: "No data yet. The daily job adds a point each day.",
    chart_marker: "today",
    chart_label_price: "Official maximum price per litre for diesel B7 and petrol E10",
    chart_label_brent: "Brent crude oil spot price in US dollar per barrel",
    show_numbers: "Show the numbers",
    col_day: "Day",
    footer:
      "Official maximum prices (incl. VAT) from FOD Economie. Brent spot price from FRED (EIA), a few working days behind.",
    source: "Source",
    headlines: { wait: "Wait", fill_up_today: "Fill up today", no_difference: "No difference" },
    market_names: { "Diesel futures": "Diesel futures", "Gasoline futures": "Gasoline futures", Brent: "Brent" },
    market_note: "Big market move: {name} {pct} since {since}.",
    reasons: {
      no_price_today: "No maximum price known for today.",
      tomorrow_only:
        "Tomorrow's maximum price is published ({tomorrow}), but today's is not stored yet, so the two cannot be compared.",
      wait_published:
        "Wait until tomorrow ({day}): the maximum price drops {cents} cent/L, {today} to {tomorrow} (published).",
      fill_published:
        "Fill up today: the maximum price rises {cents} cent/L tomorrow ({day}), {today} to {tomorrow} (published).",
      small_change: "Tomorrow's price differs by only {cents} cent/L (published).",
      shock_wait: "{name} {pct} since {since}: a drop is likely from {when} or soon after.",
      shock_fill: "{name} {pct} since {since}: a rise is likely from {when} or soon after.",
      brent_no_data: "No recent Brent price and no published change for tomorrow.",
      brent_no_base: "No Brent price from around the last price change.",
      brent_inside_band:
        "Brent {brent_from} to {brent_to} USD since {since}: inside the band, no change expected by {when}.",
      brent_wait: "Brent {brent_from} to {brent_to} USD since {since}: a drop is likely from {when}.",
      brent_fill: "Brent {brent_from} to {brent_to} USD since {since}: a rise is likely from {when}.",
    },
    caveats: {
      wholesale_proxy:
        "The wholesale diesel and petrol quotations that actually trigger a change are not free, so beyond tomorrow's published price the advice uses Brent crude as a rough stand-in.",
      bands_placeholder: "The band widths of the price rules are placeholders until calibrated on the history.",
      fx_fixed:
        "Brent and US futures are converted at a fixed EUR/USD rate. The diesel and gasoline futures are New York contracts, a stand-in for the Rotterdam quotations Belgium uses.",
      shock_prices_only: "The market shock flag looks at prices, not news: news only counts once markets move.",
      holidays_ignored: "Belgian public holidays and government price freezes are not taken into account.",
      pump_below_max: "Pump prices can be below the official maximum; the advice is about the maximum price.",
    },
  },
  nl: {
    title: "Brandstofprijzen België",
    description:
      "Officiële maximumprijzen voor diesel B7 en benzine E10 in België, met de prijs van morgen en tankadvies.",
    loading: "Prijzen laden…",
    updated: "Officiële maximumprijzen, bijgewerkt op {stamp}.",
    load_error: "De prijzen konden niet geladen worden. Probeer het later opnieuw.",
    language: "Taal",
    advice_title: "Tankadvies",
    advice_placeholder:
      "Er is nog geen advies. Het verschijnt hier zodra de dagelijkse taak het begint te publiceren.",
    advice_for: "Advies voor {day}",
    diesel: "Diesel B7",
    e10: "Benzine E10",
    today: "Vandaag",
    tomorrow: "Morgen",
    no_price_yet: "Nog geen prijs",
    since: "sinds {day}",
    not_published:
      "Nog niet gepubliceerd. FOD Economie kondigt wijzigingen aan op werkdagen, in de namiddag.",
    unchanged: "= ongewijzigd",
    up: "▲ {cents} cent hoger",
    down: "▼ {cents} cent lager",
    per_litre: " /L",
    history_title: "Maximumprijs, EUR per liter",
    brent_title: "Brent-ruwe olie, USD per vat",
    range: "Periode",
    d30: "30d",
    d90: "90d",
    d365: "1j",
    dall: "Alles",
    chart_empty: "Nog geen gegevens. De dagelijkse taak voegt elke dag een punt toe.",
    chart_marker: "vandaag",
    chart_label_price: "Officiële maximumprijs per liter voor diesel B7 en benzine E10",
    chart_label_brent: "Brent-spotprijs van ruwe olie in Amerikaanse dollar per vat",
    show_numbers: "Toon de cijfers",
    col_day: "Dag",
    footer:
      "Officiële maximumprijzen (incl. btw) van FOD Economie. Brent-spotprijs van FRED (EIA), enkele werkdagen achter.",
    source: "Bron",
    headlines: { wait: "Wacht", fill_up_today: "Tank vandaag", no_difference: "Geen verschil" },
    market_names: { "Diesel futures": "Diesel-futures", "Gasoline futures": "Benzine-futures", Brent: "Brent" },
    market_note: "Grote marktbeweging: {name} {pct} sinds {since}.",
    reasons: {
      no_price_today: "Geen maximumprijs bekend voor vandaag.",
      tomorrow_only:
        "De maximumprijs van morgen is gepubliceerd ({tomorrow}), maar die van vandaag is nog niet opgeslagen, dus ze kunnen niet vergeleken worden.",
      wait_published:
        "Wacht tot morgen ({day}): de maximumprijs daalt {cents} cent/L, van {today} naar {tomorrow} (gepubliceerd).",
      fill_published:
        "Tank vandaag: de maximumprijs stijgt morgen ({day}) met {cents} cent/L, van {today} naar {tomorrow} (gepubliceerd).",
      small_change: "De prijs van morgen verschilt maar {cents} cent/L (gepubliceerd).",
      shock_wait: "{name} {pct} sinds {since}: een daling is waarschijnlijk vanaf {when} of kort daarna.",
      shock_fill: "{name} {pct} sinds {since}: een stijging is waarschijnlijk vanaf {when} of kort daarna.",
      brent_no_data: "Geen recente Brent-prijs en geen gepubliceerde wijziging voor morgen.",
      brent_no_base: "Geen Brent-prijs rond de laatste prijswijziging.",
      brent_inside_band:
        "Brent van {brent_from} naar {brent_to} USD sinds {since}: binnen de band, geen wijziging verwacht tegen {when}.",
      brent_wait: "Brent van {brent_from} naar {brent_to} USD sinds {since}: een daling is waarschijnlijk vanaf {when}.",
      brent_fill: "Brent van {brent_from} naar {brent_to} USD sinds {since}: een stijging is waarschijnlijk vanaf {when}.",
    },
    caveats: {
      wholesale_proxy:
        "De groothandelsnoteringen voor diesel en benzine die een prijswijziging echt aansturen zijn niet gratis, dus buiten de gepubliceerde prijs van morgen gebruikt het advies ruwe olie (Brent) als grove benadering.",
      bands_placeholder:
        "De breedtes van de prijsbanden uit de regels zijn voorlopige waarden tot ze op de historiek gekalibreerd zijn.",
      fx_fixed:
        "Brent en Amerikaanse futures worden omgerekend tegen een vaste EUR/USD-koers. De diesel- en benzinefutures zijn New Yorkse contracten, een benadering van de Rotterdamse noteringen die België gebruikt.",
      shock_prices_only:
        "De marktschokvlag kijkt naar prijzen, niet naar nieuws: nieuws telt pas mee zodra de markten bewegen.",
      holidays_ignored: "Belgische feestdagen en prijsbevriezingen door de overheid worden niet meegerekend.",
      pump_below_max:
        "De pompprijs kan lager zijn dan de officiële maximumprijs; het advies gaat over de maximumprijs.",
    },
  },
};

function detectLang() {
  try {
    const saved = localStorage.getItem("lang");
    if (saved in I18N) return saved;
  } catch (e) {
    // storage can be blocked; the browser language is a fine default
  }
  const wanted = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language]) || [];
  return wanted.some((l) => String(l).toLowerCase().startsWith("nl")) ? "nl" : "en";
}

let lang = detectLang();
const locale = () => LANGS[lang];

// Look up a dotted key ("reasons.wait_published") in the current language, then English.
function t(key, params = {}) {
  const find = (table) => key.split(".").reduce((node, part) => (node == null ? node : node[part]), table);
  const text = find(I18N[lang]) ?? find(I18N.en) ?? key;
  return typeof text === "string" ? text.replace(/\{(\w+)\}/g, (m, name) => (name in params ? params[name] : m)) : key;
}

function hasText(key) {
  return key.split(".").reduce((node, part) => (node == null ? node : node[part]), I18N[lang]) != null;
}

function setLang(next) {
  lang = next;
  try {
    localStorage.setItem("lang", next);
  } catch (e) {
    // not remembered, still works
  }
}
