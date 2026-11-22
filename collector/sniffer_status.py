import time
from datetime import datetime
from zoneinfo import ZoneInfo

from firebase_admin import db

from .settings import (
    FIREBASE_NODE,
    FIREBASE_TIMEOUT_STATUS,
    TIMESTAMP_FORMAT,
    TIMEZONE,
)


def send_status():
    while True:
        try:
            # Always TIMEZONE wall time, regardless of the host's own zone.
            now = datetime.now(ZoneInfo(TIMEZONE))
            db.reference(
                f"/{FIREBASE_NODE}-{now.strftime(TIMESTAMP_FORMAT.split(' ')[0])}/status"
            ).update(
                {
                    "status": "working",
                    "timestamp": now.strftime(TIMESTAMP_FORMAT),
                }
            )
            time.sleep(FIREBASE_TIMEOUT_STATUS)
        except Exception:
            pass
