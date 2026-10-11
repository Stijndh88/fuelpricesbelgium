"""The date the advice is about: today in Belgium, not on the (UTC) runner."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

BRUSSELS = ZoneInfo("Europe/Brussels")


def today_brussels(now: datetime | None = None) -> date:
    return (now or datetime.now(BRUSSELS)).astimezone(BRUSSELS).date()
