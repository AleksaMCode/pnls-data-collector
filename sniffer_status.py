import datetime
import time

from firebase_admin import db

from settings import FIREBASE_NODE, FIREBASE_TIMEOUT_STATUS, TIMESTAMP_FORMAT


def send_status():
    while True:
        try:
            db.reference(
                f"/{FIREBASE_NODE}-{datetime.now().strftime(TIMESTAMP_FORMAT.split(' ')[0])}/status"
            ).update(
                {
                    "status": "working",
                    "timestamp": datetime.datetime.now().strftime(TIMESTAMP_FORMAT),
                }
            )
            time.sleep(FIREBASE_TIMEOUT_STATUS)
        except Exception:
            pass
