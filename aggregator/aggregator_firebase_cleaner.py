import firebase_admin
from firebase_admin import credentials

from .firebase import delete_all
from .settings import FIREBASE_CREDENTIALS, FIREBASE_DB_URL

firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)

if __name__ == "__main__":
    delete_all()
