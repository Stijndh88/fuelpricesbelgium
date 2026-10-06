import json, statistics as st, urllib.request, bisect, itertools
from datetime import date, timedelta
from fuelprices import calibrate, history, rules
from fuelprices.products import Product

UA = {"User-Agent": "Mozilla/5.0 (fuelpricesbelgium probe)"}
req = urllib.request.Request("https://petrolfed.be/nl/dms_maximumprijs_export/all/2019-01-01/2026-10-07", headers=UA)
data = {str(s["taxonomy_tid"]): {date.fromisoformat(d): float(v) for d, v in s["data"].items() if v not in (None, "")} for s in json.loads(urllib.request.urlopen(req, timeout=90).read())}
heat = data["75"]
rows = history.all_rows(history.connect("data/prices.sqlite"))
series = calibrate.build_series(rows, Product.DIESEL_B7)
proxy = dict(zip(series.days, series.costs))
actual = calibrate.real_changes(series.prices)
last = max(series.prices)
# Official cost of computation day c: the heating price valid on c+1, ex VAT, minus a constant K.
gaps = [heat[d + timedelta(days=2)] / 1.21 - proxy[d] for d in proxy if d + timedelta(days=2) in heat and d >= date(2024, 10, 1)]
K = st.median(gaps)
print("K", round(K, 4), "spread of heat minus stand-in", round(st.pstdev(gaps), 4), "EUR/L ex VAT")
days = [c for c in sorted(heat) if c.weekday() < 5 and c + timedelta(days=1) in heat and c >= date(2019, 1, 1)]
costs = [heat[c + timedelta(days=1)] / 1.21 - K for c in days]
cost_of = dict(zip(days, costs))
ser = calibrate.Series(tuple(days), tuple(costs), series.prices)
first = days[0] + timedelta(days=120); split = last - timedelta(days=180)

# 2. what the cost did on real change days (anchored on the previous real change)
eff = [a.effective_from for a in actual]
def wd(a, b):
    n, d = 0, a
    while d < b:
        d += timedelta(days=1); n += d.weekday() < 5
    return n
by_since = {}
quiet = {}
for k in range(1, len(actual)):
    comp0 = eff[k - 1] - timedelta(days=1)
    if comp0 not in cost_of or comp0 < first: continue
    base = cost_of[comp0]
    base_avg = st.mean(cost_of[d] for d in days[max(0, days.index(comp0) - 6): days.index(comp0) + 1])
    d = comp0
    while d < eff[k] - timedelta(days=1):
        d += timedelta(days=1)
        if d.weekday() >= 5 or d not in cost_of: continue
        i = days.index(d)
        avg = st.mean(costs[max(0, i - 6): i + 1])
        dd = (cost_of[d] - base) / base; da = (avg - base) / base
        s = min(wd(comp0, d), 8)
        is_change = d == eff[k] - timedelta(days=1)
        (by_since.setdefault(s, []) if is_change else quiet.setdefault(s, [])).append((dd, da, actual[k].direction))
print("days since change: real changes (n, min |day dev|, median |day dev|, min |avg dev|, median |avg dev|, same-sign share) vs quiet days (n, share with |day dev| > min-of-changes)")
for s in range(1, 9):
    ch = by_since.get(s, []); q = quiet.get(s, [])
    if not ch: continue
    adev = [abs(x[0]) for x in ch]; vdev = [abs(x[1]) for x in ch]
    sign = sum(1 for x in ch if (x[0] > 0) == (x[2] > 0)) / len(ch)
    qshare = sum(1 for x in q if abs(x[0]) > min(adev)) / max(len(q), 1)
    print(f"  {s}: n={len(ch)} day dev min {min(adev):.3f} med {st.median(adev):.3f} | avg dev min {min(vdev):.3f} med {st.median(vdev):.3f} | sign {sign:.2f} | quiet n={len(q)} share above {qshare:.2f}")

# 4. does the price step equal the cost move, measured from day to day or from 7-day averages?
import math
eff_of = {a.effective_from: a for a in actual}
res = {"day": [], "avg3": [], "avg5": [], "avg7": []}
for k in range(1, len(actual)):
    c = eff[k] - timedelta(days=1); c0 = eff[k - 1] - timedelta(days=1)
    if c not in cost_of or c0 not in cost_of or c < first: continue
    i, i0 = days.index(c), days.index(c0)
    step = actual[k].step
    for name, n in (("day", 1), ("avg3", 3), ("avg5", 5), ("avg7", 7)):
        a1 = st.mean(costs[i - n + 1:i + 1]); a0 = st.mean(costs[i0 - n + 1:i0 + 1])
        if abs(a1 - a0) > 0.003: res[name].append(step / (1.21 * (a1 - a0)))
for name, r in res.items():
    r.sort()
    q = lambda f: r[int(len(r) * f)]
    print(f"step / cost move ({name}): n={len(r)} q10 {q(0.1):.2f} q25 {q(0.25):.2f} median {q(0.5):.2f} q75 {q(0.75):.2f} q90 {q(0.9):.2f}")
# the same on 2025-26 only
# 5. how often does the heating cost (which follows the cost daily) move more than the band, without a diesel change?
for th in (0.01, 0.02, 0.03):
    n = m = 0
    for k in range(1, len(actual)):
        c0 = eff[k - 1] - timedelta(days=1); c = eff[k] - timedelta(days=1)
        if c0 not in cost_of or c0 < first: continue
        base = cost_of[c0]
        d = c0
        while d < c:
            d += timedelta(days=1)
            if d.weekday() >= 5 or d not in cost_of: continue
            if abs(cost_of[d] - base) / base > th: m += 1
            n += 1
    print(f"quiet-or-change days with |day dev| above {th:.0%}: {m} of {n}")
