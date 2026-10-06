import json, statistics as st, collections, urllib.request, bisect, itertools
from datetime import date, timedelta
from fuelprices import calibrate, history, rules
from fuelprices.products import Product

UA = {"User-Agent": "Mozilla/5.0 (fuelpricesbelgium probe)"}
req = urllib.request.Request("https://petrolfed.be/nl/dms_maximumprijs_export/all/2019-01-01/2026-10-07", headers=UA)
data = {str(s["taxonomy_tid"]): {date.fromisoformat(d): float(v) for d, v in s["data"].items() if v not in (None, "")} for s in json.loads(urllib.request.urlopen(req, timeout=90).read())}
heat = data["75"]
conn = history.connect("data/prices.sqlite")
rows = history.all_rows(conn)
series = calibrate.build_series(rows, Product.DIESEL_B7)
proxy = dict(zip(series.days, series.costs))
actual = calibrate.real_changes(series.prices)
last = max(series.prices)

def build(shift):
    # price effective on d+shift reflects the computation of day d
    cost = {}
    for d in sorted(heat):
        if d.weekday() < 5 and d + timedelta(days=shift) in heat:
            cost[d] = heat[d + timedelta(days=shift)] / 1.21
    return cost
for shift in (0, 1, 2):
    c = build(shift)
    ds = [d for d in sorted(c) if d in proxy and d - timedelta(days=1) in c and d - timedelta(days=1) in proxy and d >= date(2023, 1, 1)]
    dx = [proxy[d] - proxy[d - timedelta(days=1)] for d in ds]; dy = [c[d] - c[d - timedelta(days=1)] for d in ds]
    print("shift", shift, "corr of daily change with stand-in", round(st.correlation(dx, dy), 3), "n", len(ds))
