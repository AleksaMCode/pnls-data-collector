from datetime import timedelta, datetime

import firebase_admin
from firebase_admin import credentials

from core.orm.helpers import get_latest_import_date, import_data
from firebase import fetch_all_data, fetch_data
from settings import FIREBASE_CREDENTIALS, FIREBASE_DB_URL

firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)

LATEST_IMPORT = get_latest_import_date() + timedelta(days=1)

def transfer_all_data_from_firebase_to_db():
    data = fetch_all_data(LATEST_IMPORT)
    import_data(data)

def transfer_data():
    data = fetch_data(LATEST_IMPORT)
    import_data(data)

if __name__ == "__main__":
    transfer_all_data_from_firebase_to_db()
