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


# Words that only occur in English texts. Dutch advice must never contain them: Stijn reads the
# dashboard in Dutch, so every Dutch string comes from the templates checked here.
ENGLISH_WORDS = {
    "the", "to", "since", "from", "are", "a", "an", "and", "or", "wait", "fill",
    "drop", "rise", "likely", "possible", "guess", "price", "prices", "cost", "official",
    "inside", "expected", "change", "no", "difference", "tomorrow", "today", "by",
    "market", "move", "big", "wholesale", "published", "until", "up", "for",
}  # fmt: skip


def _english_words(text):
    import re

    return sorted(set(re.findall(r"[a-z]+", re.sub(r"\{\w+\}", " ", text).lower())) & ENGLISH_WORDS)


def test_dutch_templates_contain_no_english_words():
    texts = {f"reasons.{c}": t for c, t in messages.REASONS["nl"].items()}
    texts["market_note"] = messages.MARKET_NOTE["nl"]
    texts.update({f"caveats.{c}": v["nl"] for c, v in messages.CAVEATS.items()})
    texts.update({f"headlines.{c}": t for c, t in messages.HEADLINES["nl"].items()})
    for key, text in texts.items():
        assert not _english_words(text), (key, _english_words(text))


def test_dutch_dashboard_table_contains_no_english_words():
    import re
    from pathlib import Path

    table = (Path(__file__).parent.parent / "site" / "i18n.js").read_text(encoding="utf-8")
    dutch = table[table.index("\n  nl: {") :]
    # Product and market names are allowed to keep their English name (Brent, futures).
    for text in re.findall(r':\s*"([^"\n]{12,})"', dutch):
        assert not _english_words(text), (text, _english_words(text))


def test_dutch_page_never_shows_the_english_advice_text():
    from pathlib import Path

    app = (Path(__file__).parent.parent / "site" / "app.js").read_text(encoding="utf-8")
    assert 'lang === "nl" && fallback ? t("advice_unknown")' in app


def test_every_headline_exists_in_both_languages_and_the_dashboard():
    from pathlib import Path

    assert set(messages.HEADLINES["en"]) == set(messages.HEADLINES["nl"])
    table = (Path(__file__).parent.parent / "site" / "i18n.js").read_text(encoding="utf-8")
    for action in messages.HEADLINES["en"]:
        assert table.count(f"{action}: ") >= 2, action
    assert messages.headline("fill_by", "nl", {"day": "2026-10-09"}) == "Tank uiterlijk vr 09/10"
