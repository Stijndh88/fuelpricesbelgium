from datetime import date

from fuelprices import crude

FRED_SAMPLE = """observation_date,DCOILBRENTEU
2026-09-28,96.81
2026-09-29,.
2026-09-30,99.95
2026-10-01,103.12
"""


def test_parse_fred_csv_skips_missing_values():
    assert crude.parse_fred_csv(FRED_SAMPLE) == {
        date(2026, 9, 28): 96.81,
        date(2026, 9, 30): 99.95,
        date(2026, 10, 1): 103.12,
    }


def test_parse_fred_csv_accepts_old_header_and_blank_lines():
    text = "DATE,DCOILBRENTEU\n2026-10-01,101.5\n\n"
    assert crude.parse_fred_csv(text) == {date(2026, 10, 1): 101.5}
