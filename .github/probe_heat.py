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

# 1. free-running replay with the existing grid
res = []
for params in calibrate.grid():
    rep = calibrate.replay(Product.DIESEL_B7, ser, params)
    res.append((calibrate.score_changes(rep, actual, first, split).f1, params))
res.sort(key=lambda r: -r[0])
print("free-running replay, top 4 by fit F1")
for f1, p in res[:4]:
    rep = calibrate.replay(Product.DIESEL_B7, ser, p)
    tr = calibrate.score_changes(rep, actual, first, split); te = calibrate.score_changes(rep, actual, split + timedelta(days=1), last)
    print("  ", p, "fit P/R", round(tr.precision, 2), round(tr.recall, 2), "held-out P/R", round(te.precision, 2), round(te.recall, 2), "n", te.real_changes, "exact", te.same_day)

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

# 3. anchored one-step prediction with the official cost
def anchored(start, end, mode, recenter, lag=0):
    sched = calibrate.Params(start, end, lag, recenter).schedule()
    preds = {}
    for d in days:
        if d < first or d > last: continue
        k = bisect.bisect_right(eff, d) - 1
        if k < 0: continue
        comp0 = eff[k] - timedelta(days=1)
        if comp0 not in cost_of: continue
        i = days.index(d); j = days.index(comp0)
        if i < 7 or j < 7: continue
        base = costs[j] if recenter == "day" else st.mean(costs[j - 6:j + 1])
        th = sched.at(max(wd(comp0, d), 1))
        today = costs[i - lag]; avg = st.mean(costs[i - lag - 6:i - lag + 1])
        dd = (today - base) / base; da = (avg - base) / base
        if mode == "both": up, dn = dd > th and da > th, dd < -th and da < -th
        elif mode == "day": up, dn = dd > th, dd < -th
        else: up, dn = da > th, da < -th
        preds[d] = 1 if up else (-1 if dn else 0)
    return preds
def score(preds, a, b):
    real = {x.effective_from: x.direction for x in actual if a <= x.effective_from <= b}
    tp = fp = fn = 0
    for d, p in preds.items():
        e = d + timedelta(days=1)
        if not a <= e <= b: continue
        r = real.get(e, 0)
        if p:
            if r == p: tp += 1
            else: fp += 1
        elif r: fn += 1
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    return P, R, 2 * P * R / (P + R) if P + R else 0, tp + fn
cands = []
for s, e in itertools.product([x / 1000 for x in range(5, 61, 5)], [x / 1000 for x in range(5, 61, 5)]):
    if e > s: continue
    for mode, rc in itertools.product(("both", "day", "avg"), ("day", "average")):
        pr = anchored(s, e, mode, rc)
        cands.append((score(pr, first, split)[2], (s, e, mode, rc), pr))
cands.sort(key=lambda r: -r[0])
print("anchored one-step prediction with the official cost, top 6 by fit F1 (exact day)")
for f, p, pr in cands[:6]:
    tr = score(pr, first, split); te = score(pr, split + timedelta(days=1), last)
    print("  ", p, "fit P/R", round(tr[0], 2), round(tr[1], 2), "held-out P/R", round(te[0], 2), round(te[1], 2), "n", te[3])
