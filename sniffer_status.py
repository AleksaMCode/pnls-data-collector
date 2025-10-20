import datetime
import time

from firebase_admin import db

from settings import FIREBASE_NODE, FIREBASE_TIMEOUT_STATUS


def send_status():
    while True:
        try:
            db.reference(f"/{FIREBASE_NODE}/status").update(
                {
                    "ssid": "working",
                    "timestamp": datetime.datetime.now().strftime("%Y%m%d"),
                }
            )
            time.sleep(FIREBASE_TIMEOUT_STATUS)
        except Exception:
            pass
