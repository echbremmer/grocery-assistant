from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from grocery_assistant.scheduler import cron_trigger

TZ = "Europe/Amsterdam"
SAT = datetime(2026, 11, 21, 12, 0, tzinfo=ZoneInfo(TZ))  # Saturday


@pytest.mark.parametrize(
    ("expr", "expected_day"),
    [
        ("0 8 * * 1", 23),       # Monday (APScheduler's from_crontab would say Tuesday)
        ("0 8 * * mon", 23),
        ("0 8 * * 0", 22),       # Sunday
        ("0 8 * * 7", 22),       # Sunday, cron alias
        ("0 8 * * 5", 27),       # Friday
        ("0 8 * * 1-5", 23),     # weekdays: next is Monday
        ("0 8 * * 0,6", 22),     # Sat 08:00 already passed: Sunday
    ],
)
def test_cron_weekdays_like_cron(expr, expected_day):
    nxt = cron_trigger(expr, TZ).get_next_fire_time(None, SAT)
    assert (nxt.day, nxt.hour, nxt.minute) == (expected_day, 8, 0)
