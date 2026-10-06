"use strict";

// Static dashboard: reads data/prices.json (written by `python -m fuelprices.export`) and
// data/advice.json (written by the refuel advice job, optional) and draws everything client-side.

const PRODUCTS = [
  { key: "diesel", adviceKey: "diesel_b7", color: "--series-1" },
  { key: "e10", adviceKey: "e10", color: "--series-2" },
].map((p) => ({
  ...p,
  get label() {
    return t(p.key);
  },
}));
const DAY_MS = 86400000;
const SVG_NS = "http://www.w3.org/2000/svg";

const brusselsToday = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Brussels" }).format(new Date());
const dayNumber = (iso) => Date.parse(iso + "T00:00:00Z") / DAY_MS;
const fmtDay = (iso, opts = { weekday: "short", day: "numeric", month: "short" }) =>
  new Date(iso + "T00:00:00Z").toLocaleDateString(locale(), { timeZone: "UTC", ...opts });
const fmtShortDay = (iso) => fmtDay(iso, { day: "numeric", month: "short" });
const num = (v, digits) =>
  new Intl.NumberFormat(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v);
const fmtEur = (v) => (v == null ? "–" : "€" + num(v, 3));
const fmtUsd = (v) => (v == null ? "–" : "$" + num(v, 2));
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function el(tag, attrs = {}, text) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}
function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}

async function getJson(url) {
  const response = await fetch(url, { cache: "no-cache" });
  if (!response.ok) throw new Error(url + ": " + response.status);
  return response.json();
}

// ---- Tiles: price today and the already published price for tomorrow ----

function renderTiles(days, today) {
  const box = document.getElementById("tiles");
  box.replaceChildren();
  for (const p of PRODUCTS) {
    const known = days.filter((d) => d[p.key] != null);
    const current = [...known].reverse().find((d) => d.day <= today);
    const next = known.find((d) => d.day > today);

    const tile = el("div", { class: "tile" });
    const label = el("div", { class: "tile-label" });
    const key = el("span", { class: "key" });
    key.style.background = `var(${p.color})`;
    label.append(key, document.createTextNode(p.label));
    tile.append(label);

    const rows = el("div", { class: "tile-rows" });
    const nowCol = el("div");
    nowCol.append(el("div", { class: "tile-when" }, current ? t("today") : t("no_price_yet")));
    if (current) {
      const value = el("div", { class: "tile-value" }, fmtEur(current[p.key]));
      value.append(el("small", {}, t("per_litre")));
      nowCol.append(value);
      if (current.day !== today) nowCol.append(el("div", { class: "tile-when" }, t("since", { day: fmtDay(current.day) })));
    }
    rows.append(nowCol);

    const nextCol = el("div");
    if (next) {
      nextCol.append(el("div", { class: "tile-when" }, fmtDay(next.day)));
      const value = el("div", { class: "tile-value" }, fmtEur(next[p.key]));
      value.append(el("small", {}, t("per_litre")));
      nextCol.append(value);
      if (current) nextCol.append(deltaNode(next[p.key] - current[p.key]));
    } else {
      nextCol.append(el("div", { class: "tile-when" }, t("tomorrow")));
      nextCol.append(
        el("div", { class: "tile-pending" }, t("not_published")),
      );
    }
    rows.append(nextCol);
    tile.append(rows);
    box.append(tile);
  }
}

function deltaNode(diff) {
  const cents = Math.round(diff * 1000) / 10;
  if (cents === 0) return el("div", { class: "delta same" }, t("unchanged"));
  const up = cents > 0;
  return el(
    "div",
    { class: "delta " + (up ? "up" : "down") },
    t(up ? "up" : "down", { cents: num(Math.abs(cents), 1) }),
  );
}

// ---- Refuel advice (optional file) ----

// Turn the parameters that come with a reason code into display text for the current language.
function adviceParams(params = {}) {
  const out = {};
  for (const [key, value] of Object.entries(params)) {
    if (["day", "when"].includes(key)) out[key] = fmtDay(value);
    else if (key === "since") out[key] = fmtShortDay(value);
    else if (key === "pct") out[key] = (value > 0 ? "+" : "") + num(value, 1) + "%";
    else if (key === "name") out[key] = hasText("market_names." + value) ? t("market_names." + value) : value;
    else if (["today", "tomorrow"].includes(key)) out[key] = num(value, 3);
    else if (key === "cents") out[key] = num(value, 1);
    else if (typeof value === "number") out[key] = num(value, 0);
    else out[key] = value;
  }
  return out;
}

// The advice text in the current language: from its code when the page knows it, otherwise
// the English sentence the advice job wrote.
function adviceText(codeKey, code, params, fallback) {
  const key = codeKey + "." + code;
  return code && hasText(key) ? t(key, adviceParams(params)) : fallback;
}

function renderAdvice(data) {
  // Shape written by `fuelprices advise --json data/advice.json` (see fuelprices.advice).
  const box = document.getElementById("advice");
  const list = (data && Array.isArray(data.advice) && data.advice) || [];
  const items = PRODUCTS.map((p) => [p, list.find((a) => a.product === p.adviceKey)])
    .filter(([, a]) => a)
    .map(([p, a]) => {
      const item = el("div", { class: "advice-item " + String(a.action || "").replace(/[^a-z_]/g, "") });
      const headline = hasText("headlines." + a.action) ? t("headlines." + a.action) : a.headline || a.action || "–";
      item.append(el("div", { class: "advice-head" }, `${p.label}: ${headline}`));
      const reason = adviceText("reasons", a.reason_code, a.reason_params, a.reason);
      if (reason) item.append(el("div", { class: "advice-reason" }, reason));
      if (a.market_note) {
        const note = a.market_note_params
          ? t("market_note", adviceParams(a.market_note_params))
          : a.market_note;
        item.append(el("div", { class: "advice-reason" }, "⚠ " + note));
      }
      return item;
    });
  if (!items.length) {
    box.replaceChildren(el("p", { class: "muted" }, t("advice_placeholder")));
    return;
  }
  box.replaceChildren(...items);
  const codes = Array.isArray(data.caveat_codes) ? data.caveat_codes : [];
  const caveats = (Array.isArray(data.caveats) ? data.caveats : []).map((text, i) =>
    codes[i] && hasText("caveats." + codes[i]) ? t("caveats." + codes[i]) : text,
  );
  if (caveats.length) box.append(el("p", { class: "muted" }, caveats.join(" ")));
  if (data.as_of) box.append(el("p", { class: "muted" }, t("advice_for", { day: fmtDay(data.as_of) })));
}

// ---- Line chart with crosshair tooltip ----

function niceTicks(min, max, count) {
  const span = max - min || Math.abs(max) || 1;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(+v.toFixed(10));
  return { ticks, step };
}

function lineChart(container, { days, series, format, tickFormat, step = false, today }) {
  container.replaceChildren();
  const points = series.map((s) => days.filter((d) => d[s.key] != null).map((d) => ({ day: d.day, x: dayNumber(d.day), y: d[s.key] })));
  const all = points.flat();
  if (all.length === 0) {
    container.append(el("p", { class: "empty" }, t("chart_empty")));
    return;
  }

  const width = container.clientWidth;
  const height = container.clientHeight;
  const m = { top: 10, right: 52, bottom: 24, left: 44 };
  const w = width - m.left - m.right;
  const h = height - m.top - m.bottom;

  let x0 = Math.min(...all.map((p) => p.x));
  let x1 = Math.max(...all.map((p) => p.x));
  if (x0 === x1) { x0 -= 1; x1 += 1; }
  let ymin = Math.min(...all.map((p) => p.y));
  let ymax = Math.max(...all.map((p) => p.y));
  const pad = (ymax - ymin) * 0.1 || Math.abs(ymax) * 0.02 || 1;
  const { ticks, step: yStep } = niceTicks(ymin - pad, ymax + pad, 4);
  ymin = Math.min(ticks[0], ymin - pad);
  ymax = Math.max(ticks[ticks.length - 1], ymax + pad);

  const sx = (x) => m.left + ((x - x0) / (x1 - x0)) * w;
  const sy = (y) => m.top + h - ((y - ymin) / (ymax - ymin)) * h;

  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": container.dataset.label || "" });

  const grid = svg("g", { class: "grid" });
  for (const t of ticks) {
    if (t < ymin || t > ymax) continue;
    grid.append(svg("line", { x1: m.left, x2: m.left + w, y1: sy(t), y2: sy(t) }));
    root.append(svg("text", { class: "tick", x: m.left - 6, y: sy(t) + 4, "text-anchor": "end" }, tickFormat(t, yStep)));
  }
  root.prepend(grid);
  root.append(svg("line", { class: "axis-line", x1: m.left, x2: m.left + w, y1: m.top + h, y2: m.top + h }));

  // A handful of date ticks, never crowding on a phone.
  const xTickCount = Math.max(2, Math.min(5, Math.floor(w / 90)));
  const spanDays = x1 - x0;
  const seenTicks = new Set();
  for (let i = 0; i <= xTickCount; i++) {
    const x = Math.round(x0 + (spanDays * i) / xTickCount);
    if (seenTicks.has(x)) continue;
    seenTicks.add(x);
    const iso = new Date(x * DAY_MS).toISOString().slice(0, 10);
    const opts = spanDays > 300 ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" };
    const anchor = i === 0 ? "start" : i === xTickCount ? "end" : "middle";
    root.append(svg("text", { class: "tick", x: sx(x), y: m.top + h + 16, "text-anchor": anchor }, fmtDay(iso, opts)));
  }

  // "Today" marker when future (already published) prices are on the chart.
  if (today && dayNumber(today) < x1 && dayNumber(today) >= x0) {
    root.append(svg("line", { class: "axis-line", x1: sx(dayNumber(today)), x2: sx(dayNumber(today)), y1: m.top, y2: m.top + h }));
    if (sx(dayNumber(today)) - m.left > 40) {
      root.append(svg("text", { class: "tick", x: sx(dayNumber(today)) - 4, y: m.top + 10, "text-anchor": "end" }, t("chart_marker")));
    }
  }

  series.forEach((s, i) => {
    const pts = points[i];
    if (!pts.length) return;
    const color = cssVar(s.color);
    let d = "";
    pts.forEach((p, j) => {
      if (j === 0) d += `M${sx(p.x)},${sy(p.y)}`;
      else if (step) d += `H${sx(p.x)}V${sy(p.y)}`;
      else d += `L${sx(p.x)},${sy(p.y)}`;
    });
    root.append(svg("path", { d, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    const last = pts[pts.length - 1];
    root.append(svg("circle", { class: "dot", cx: sx(last.x), cy: sy(last.y), r: 4, fill: color }));
    root.append(svg("text", { class: "end-label", x: sx(last.x) + 7, y: sy(last.y) + 4 }, format(last.y)));
  });

  // Hover layer: the crosshair snaps to the nearest day with data.
  const hoverDays = days.filter((d) => series.some((s) => d[s.key] != null));
  const cross = svg("line", { class: "crosshair", y1: m.top, y2: m.top + h, visibility: "hidden" });
  const hoverDots = series.map((s) => svg("circle", { class: "dot", r: 4, fill: cssVar(s.color), visibility: "hidden" }));
  root.append(cross, ...hoverDots);
  const hit = svg("rect", { x: m.left, y: 0, width: w + m.right, height: height, fill: "transparent", tabindex: 0 });
  root.append(hit);
  container.append(root);

  const tooltip = document.getElementById("tooltip");
  let index = hoverDays.length - 1;
  const show = (i, clientX, clientY) => {
    index = Math.max(0, Math.min(hoverDays.length - 1, i));
    const day = hoverDays[index];
    const x = sx(dayNumber(day.day));
    cross.setAttribute("x1", x);
    cross.setAttribute("x2", x);
    cross.setAttribute("visibility", "visible");
    series.forEach((s, j) => {
      const v = valueAt(days, s.key, day.day, step);
      hoverDots[j].setAttribute("visibility", v == null ? "hidden" : "visible");
      if (v != null) { hoverDots[j].setAttribute("cx", x); hoverDots[j].setAttribute("cy", sy(v)); }
    });
    tooltip.replaceChildren(el("div", { class: "tt-day" }, fmtDay(day.day, { weekday: "short", day: "numeric", month: "short", year: "numeric" })));
    for (const s of series) {
      const row = el("div", { class: "tt-row" });
      const key = el("span", { class: "key" });
      key.style.background = `var(${s.color})`;
      row.append(key, el("strong", {}, format(valueAt(days, s.key, day.day, step))), el("span", {}, s.label));
      tooltip.append(row);
    }
    tooltip.hidden = false;
    const box = container.getBoundingClientRect();
    const tx = clientX ?? box.left + x;
    const ty = clientY ?? box.top + m.top;
    const tw = tooltip.offsetWidth;
    tooltip.style.left = Math.min(window.innerWidth - tw - 8, Math.max(8, tx + 12)) + "px";
    tooltip.style.top = Math.max(8, ty - tooltip.offsetHeight - 12) + "px";
  };
  const hide = () => {
    cross.setAttribute("visibility", "hidden");
    hoverDots.forEach((dot) => dot.setAttribute("visibility", "hidden"));
    tooltip.hidden = true;
  };
  const nearest = (clientX) => {
    const box = root.getBoundingClientRect();
    const xVal = x0 + ((clientX - box.left - m.left) / w) * (x1 - x0);
    let best = 0;
    hoverDays.forEach((d, i) => {
      if (Math.abs(dayNumber(d.day) - xVal) < Math.abs(dayNumber(hoverDays[best].day) - xVal)) best = i;
    });
    return best;
  };
  hit.addEventListener("pointermove", (e) => show(nearest(e.clientX), e.clientX, e.clientY));
  hit.addEventListener("pointerdown", (e) => show(nearest(e.clientX), e.clientX, e.clientY));
  hit.addEventListener("pointerleave", hide);
  hit.addEventListener("focus", () => show(index));
  hit.addEventListener("blur", hide);
  hit.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { show(index - 1); e.preventDefault(); }
    if (e.key === "ArrowRight") { show(index + 1); e.preventDefault(); }
  });
}

// The value in force on a day: for step series (max prices) the last known value before it.
function valueAt(days, key, iso, step) {
  if (!step) return (days.find((d) => d.day === iso) || {})[key] ?? null;
  let value = null;
  for (const d of days) {
    if (d.day > iso) break;
    if (d[key] != null) value = d[key];
  }
  return value;
}

// ---- Table view ----

function renderTable(days) {
  const body = document.querySelector("#table tbody");
  body.replaceChildren(
    ...[...days].reverse().map((d) => {
      const tr = el("tr");
      tr.append(el("td", {}, fmtDay(d.day, { day: "2-digit", month: "short", year: "numeric" })), el("td", {}, fmtEur(d.diesel)), el("td", {}, fmtEur(d.e10)), el("td", {}, fmtUsd(d.brent)));
      return tr;
    }),
  );
}

// ---- Page ----

const state = { days: [], generatedAt: null, advice: null, loaded: false, rangeDays: 90, today: brusselsToday() };

function visibleDays() {
  if (!state.rangeDays) return state.days;
  const from = dayNumber(state.today) - state.rangeDays;
  return state.days.filter((d) => dayNumber(d.day) >= from);
}

function renderCharts() {
  const days = visibleDays();
  const priceChart = document.getElementById("price-chart");
  priceChart.dataset.label = t("chart_label_price");
  lineChart(priceChart, {
    days,
    series: PRODUCTS,
    step: true,
    today: state.today,
    format: fmtEur,
    tickFormat: (v, s) => "€" + num(v, s < 0.01 ? 3 : 2),
  });
  const brentChart = document.getElementById("brent-chart");
  brentChart.dataset.label = t("chart_label_brent");
  lineChart(brentChart, {
    days,
    series: [{ key: "brent", label: "Brent", color: "--brent" }],
    format: fmtUsd,
    tickFormat: (v, s) => "$" + num(v, s < 1 ? 1 : 0),
  });
}

function renderLegend() {
  const legend = document.getElementById("price-legend");
  legend.replaceChildren(
    ...PRODUCTS.map((p) => {
      const item = el("span");
      const key = el("span", { class: "key" });
      key.style.background = `var(${p.color})`;
      item.append(key, document.createTextNode(p.label));
      return item;
    }),
  );
}

// Text that is in the HTML: data-i18n sets the text, data-i18n-attr the named attribute.
function applyStaticText() {
  document.documentElement.lang = lang;
  document.title = t("title");
  document.querySelector('meta[name="description"]').setAttribute("content", t("description"));
  for (const node of document.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
  for (const node of document.querySelectorAll("[data-i18n-label]")) node.setAttribute("aria-label", t(node.dataset.i18nLabel));
  for (const button of document.querySelectorAll("#lang button")) button.setAttribute("aria-pressed", String(button.dataset.lang === lang));
}

function renderAll() {
  applyStaticText();
  const updated = document.getElementById("updated");
  if (!state.loaded) return;
  const stamp = state.generatedAt
    ? new Date(state.generatedAt).toLocaleString(locale(), { timeZone: "Europe/Brussels", dateStyle: "medium", timeStyle: "short" })
    : "?";
  updated.textContent = t("updated", { stamp });
  renderTiles(state.days, state.today);
  renderLegend();
  renderCharts();
  renderTable(state.days);
  renderAdvice(state.advice);
}

async function main() {
  applyStaticText();
  const updated = document.getElementById("updated");
  let prices;
  try {
    prices = await getJson("data/prices.json");
  } catch (err) {
    updated.textContent = t("load_error");
    console.error(err);
    return;
  }
  state.days = prices.days || [];
  state.generatedAt = prices.generated_at || null;
  state.loaded = true;
  renderAll();

  document.getElementById("range").addEventListener("click", (e) => {
    const button = e.target.closest("button");
    if (!button) return;
    state.rangeDays = Number(button.dataset.days);
    for (const b of e.currentTarget.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === button));
    renderCharts();
  });
  document.getElementById("lang").addEventListener("click", (e) => {
    const button = e.target.closest("button");
    if (!button || button.dataset.lang === lang) return;
    setLang(button.dataset.lang);
    renderAll();
  });
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(renderCharts, 150);
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderCharts);

  getJson("data/advice.json").then(
    (data) => {
      state.advice = data;
      renderAdvice(data);
    },
    () => {},
  );
}

main();
