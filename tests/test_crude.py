import json
from datetime import date

from fuelprices import crude

# Trimmed from a live https://query1.finance.yahoo.com/v8/finance/chart/BZ=F response.
YAHOO_SAMPLE = json.dumps(
    {
        "chart": {
            "result": [
                {
                    "meta": {"currency": "USD", "symbol": "BZ=F"},
                    "timestamp": [1790726400, 1790812800, 1790899200, 1791158400],
                    "indicators": {"quote": [{"close": [96.81, None, 103.1234, 99.05]}]},
                }
            ],
            "error": None,
        }
    }
)


def test_parse_yahoo_chart_skips_missing_closes():
    assert crude.parse_yahoo_chart(YAHOO_SAMPLE) == {
        date(2026, 9, 30): 96.81,
        date(2026, 10, 2): 103.12,
        date(2026, 10, 5): 99.05,
    }


def test_parse_yahoo_chart_without_bars():
    empty = {"chart": {"result": [{"meta": {}, "indicators": {"quote": [{"close": []}]}}]}}
    assert crude.parse_yahoo_chart(json.dumps(empty)) == {}
