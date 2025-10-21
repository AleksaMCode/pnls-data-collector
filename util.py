from datetime import datetime, time
from zoneinfo import ZoneInfo

from settings import TIMEZONE


def is_working_hours(tz=TIMEZONE):
    """
    Returns True if the current time is between 7 AM and 6 PM.
    """
    now = datetime.now(ZoneInfo(tz)).time()
    return time(7, 0) <= now <= time(18, 0)
