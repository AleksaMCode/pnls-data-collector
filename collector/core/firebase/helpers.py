from datetime import datetime

import firebase_admin
from firebase_admin import credentials, db

from collector.settings import (
    FIREBASE_CREDENTIALS,
    FIREBASE_DB_URL,
    FIREBASE_NODE,
    TIMESTAMP_FORMAT,
)

# Init Firebase DB
firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)


def publish_captured_date(data, timestamp):
    """
    Publishes captured probe request data to Firebase Realtime DB.
    """
    db.reference(f"/{FIREBASE_NODE}-{timestamp}/data").push(data)


def update_device_status():
    """
    Updates the current device status in the Firebase Realtime DB.
    """
    db.reference(
        f"/{FIREBASE_NODE}-{datetime.now().strftime(TIMESTAMP_FORMAT.split(' ')[0])}/status"
    ).update(
        {  # TODO: Maybe implement status as a Enum.
            "status": "working",
            "timestamp": datetime.now().strftime(TIMESTAMP_FORMAT),
        }
    )
