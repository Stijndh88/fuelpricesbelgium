import json
from datetime import UTC, date, datetime

from fuelprices import export, history
from fuelprices.history import DailyPrices

NOW = datetime(2026, 10, 6, 16, 0, tzinfo=UTC)


def test_export_writes_days_in_order(tmp_path):
    conn = history.connect(tmp_path / "prices.sqlite")
    history.upsert(conn, DailyPrices(day=date(2026, 10, 7), diesel_max=2.392, e10_max=2.065))
    history.upsert(conn, DailyPrices(day=date(2026, 10, 6), diesel_max=2.432, brent_usd=99.5))
    out = tmp_path / "site" / "data" / "prices.json"

    export.export(conn, out, now=NOW)

    data = json.loads(out.read_text())
    assert data["generated_at"] == "2026-10-06T16:00:00+00:00"
    assert data["days"] == [
        {"day": "2026-10-06", "diesel": 2.432, "e10": None, "brent": 99.5},
        {"day": "2026-10-07", "diesel": 2.392, "e10": 2.065, "brent": None},
    ]


def test_export_skips_empty_days():
    rows = [DailyPrices(day=date(2026, 10, 5)), DailyPrices(day=date(2026, 10, 6), e10_max=2.0)]
    assert [d["day"] for d in export.to_json(rows, NOW)["days"]] == ["2026-10-06"]
