from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def scalar_to_int(value) -> int:
    return int(value or 0)


def today_in_tz(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()


def last_n_dates_excluding_today(n_days: int, tz: str) -> list[date]:
    today = today_in_tz(tz)
    return [today - timedelta(days=delta) for delta in range(n_days, 0, -1)]


def previous_n_dates_before_last_n(n_days: int, tz: str) -> list[date]:
    today = today_in_tz(tz)
    start_days_ago = 2 * n_days
    end_days_ago = n_days + 1
    return [
        today - timedelta(days=delta)
        for delta in range(start_days_ago, end_days_ago - 1, -1)
    ]
