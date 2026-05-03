import firebase_admin
from firebase_admin import credentials, db

from aggregator.settings import (
    FIREBASE_CREDENTIALS,
    FIREBASE_DB_URL,
    FIREBASE_STATISTICS_NODE,
)

firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)


def fix():
    db.reference(f"/{FIREBASE_STATISTICS_NODE}/daily/2026-02-28/RPI-1").update(
        {
            "ssid": 199,
            "mac": 2636,
            "probe_requests": 20421,
        }
    )

    db.reference(f"/{FIREBASE_STATISTICS_NODE}/daily/2026-02-28/RPI-2").update(
        {
            "ssid": 57,
            "mac": 613,
            "probe_requests": 2927,
        }
    )

    db.reference(f"/{FIREBASE_STATISTICS_NODE}/daily/2026-02-28/RPI-3").update(
        {
            "ssid": 53,
            "mac": 254,
            "probe_requests": 2047,
        }
    )


if __name__ == "__main__":
    fix()
