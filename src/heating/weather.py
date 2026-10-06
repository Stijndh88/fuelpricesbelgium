"""Daily mean outdoor temperature from Open-Meteo (free, no API key).

The forecast endpoint returns the last ``past_days`` as well, so one call covers the recent
past and the coming week.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def parse(text: str) -> dict[date, float]:
    """Parse an Open-Meteo daily response into {day: mean temperature in deg C}."""
    daily = json.loads(text)["daily"]
    return {
        date.fromisoformat(day): float(temp)
        for day, temp in zip(daily["time"], daily["temperature_2m_mean"], strict=True)
        if temp is not None
    }


def fetch_daily_means(
    latitude: float, longitude: float, past_days: int = 7, forecast_days: int = 7, timeout=30
) -> dict[date, float]:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_mean",
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "Europe/Brussels",
        }
    )
    request = urllib.request.Request(
        f"{FORECAST_URL}?{query}", headers={"User-Agent": "fuelpricesbelgium"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse(response.read().decode("utf-8"))
