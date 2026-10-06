from fuelprices import advice, messages


def test_every_code_has_both_languages_and_the_same_parameters():
    assert set(messages.REASONS["nl"]) == set(messages.REASONS["en"])
    import string

    for code, english in messages.REASONS["en"].items():
        names = {f for _, f, _, _ in string.Formatter().parse(english) if f}
        dutch = {f for _, f, _, _ in string.Formatter().parse(messages.REASONS["nl"][code]) if f}
        assert names == dutch, code
    for entry in messages.CAVEATS.values():
        assert set(entry) == {"en", "nl"}


def test_advice_json_carries_codes_for_every_text(tmp_path):
    from datetime import date, timedelta

    from fuelprices import history
    from fuelprices.history import DailyPrices

    conn = history.connect(tmp_path / "p.sqlite")
    day = date(2026, 10, 6)
    history.upsert(conn, DailyPrices(day=day, diesel_max=2.432, e10_max=2.07))
    history.upsert(conn, DailyPrices(day=day + timedelta(days=1), diesel_max=2.392))
    data = advice.export(conn, day)
    diesel, e10 = data["advice"]
    assert diesel["reason_code"] == "wait_published"
    assert (
        diesel["reason_params"]["cents"] == 4.0 and diesel["reason_params"]["day"] == "2026-10-07"
    )
    assert e10["reason_code"] in messages.REASONS["en"]
    assert data["caveat_codes"] == list(messages.CAVEATS)
    assert len(data["caveat_codes"]) == len(data["caveats"])


def test_dashboard_table_has_every_code_in_both_languages():
    from pathlib import Path

    table = (Path(__file__).parent.parent / "site" / "i18n.js").read_text(encoding="utf-8")
    for code in [*messages.REASONS["en"], *messages.CAVEATS]:
        assert table.count(f"\n      {code}:") == 2, code
