import firebase_admin
from firebase_admin import credentials

from aggregator.core.mongo.helpers import insert_from_firebase_to_mongo

from .firebase import delete_all_by_nodes, download_all
from .settings import FIREBASE_CREDENTIALS, FIREBASE_DB_URL

firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)

if __name__ == "__main__":
    data = download_all()
    insert_from_firebase_to_mongo(data)
    delete_all_by_nodes()
