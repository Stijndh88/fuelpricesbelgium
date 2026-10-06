import json, statistics as st, collections, urllib.request
from datetime import date, timedelta
from fuelprices import calibrate, history, rules
from fuelprices.products import Product

UA = {"User-Agent": "Mozilla/5.0 (fuelpricesbelgium probe)"}
def fetch(a, b):
    req = urllib.request.Request(f"https://petrolfed.be/nl/dms_maximumprijs_export/all/{a}/{b}", headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=90).read())
data = {}
for ser in fetch("2011-01-01", "2026-10-07"):
    data[str(ser["taxonomy_tid"])] = (ser["titel"], {date.fromisoformat(d): float(v) for d, v in ser["data"].items() if v not in (None, "")})
for tid in ("35", "36", "75", "124", "31"):
    t, d = data[tid]
    days = sorted(d)
    ch = [(b, d[b] - d[a]) for a, b in zip(days, days[1:]) if abs(d[b] - d[a]) > 1e-9]
    print("tid", tid, t, "first", days[0], "n", len(days), "changes", len(ch), "last-year changes", sum(1 for x, _ in ch if x >= date(2025, 10, 7)))
    wd = collections.Counter(x.weekday() for x, _ in ch); print("   weekday", dict(sorted(wd.items())))
    big = [(x.isoformat(), round(v, 3)) for x, v in ch if abs(v) > 0.12]
    print("   big moves", big[:12])
conn = history.connect("data/prices.sqlite")
rows = history.all_rows(conn)
series = calibrate.build_series(rows, Product.DIESEL_B7)
cost_on = dict(zip(series.days, series.costs))  # EUR/L stand-in
for tid in ("75", "35"):
    heat = data[tid][1]
    common = [d for d in series.days if d in heat and d >= date(2023, 1, 1)]
    xs = [cost_on[d] for d in common]; ys = [heat[d] / 1.21 for d in common]
    print("tid", tid, "common days", len(common), "corr level", round(st.correlation(xs, ys), 4))
    dx = [b - a for a, b in zip(xs, xs[1:])]; dy = [b - a for a, b in zip(ys, ys[1:])]
    print("   corr daily change", round(st.correlation(dx, dy), 3))
    # slope of heat on stand-in changes
    print("   slope heat per proxy change", round(st.correlation(dx, dy) * st.pstdev(dy) / st.pstdev(dx), 3))
heat = data["75"][1] if len(data["75"][1]) > 2000 else data["35"][1]
print("heating series used first day", min(heat))
# implied cost series (EUR/L ex VAT, minus constant K estimated against the stand-in over the last 2 years)
recent = [d for d in series.days if d in heat and d >= date(2024, 10, 1)]
K = st.median(heat[d] / 1.21 - cost_on[d] for d in recent)
print("K (heat ex VAT minus stand-in), EUR/L", round(K, 4), "spread", round(st.pstdev([heat[d] / 1.21 - cost_on[d] for d in recent]), 4))
days = [d for d in sorted(heat) if d.weekday() < 5 or True]
costs = [heat[d] / 1.21 - K for d in days]
ser = calibrate.Series(tuple(days), tuple(costs), series.prices)
actual = calibrate.real_changes(series.prices)
first = days[0] + timedelta(days=120); last = max(series.prices); split = last - timedelta(days=180)
res = []
for params in calibrate.grid():
    rep = calibrate.replay(Product.DIESEL_B7, ser, params)
    res.append((calibrate.score_changes(rep, actual, first, split).f1, params))
res.sort(key=lambda r: -r[0])
for f1, params in res[:5]:
    rep = calibrate.replay(Product.DIESEL_B7, ser, params)
    tr = calibrate.score_changes(rep, actual, first, split); te = calibrate.score_changes(rep, actual, split + timedelta(days=1), last)
    print(params, "fit P/R", round(tr.precision, 2), round(tr.recall, 2), "test P/R", round(te.precision, 2), round(te.recall, 2), "n", te.real_changes, "exact", te.same_day)
