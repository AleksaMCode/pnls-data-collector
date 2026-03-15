from collections import defaultdict

import firebase_admin
from firebase_admin import credentials, db
from yaspin import yaspin

from firebase_housekeeping.settings import (
    FIREBASE_CREDENTIALS,
    FIREBASE_DB_URL,
    FIREBASE_STATISTICS_NODE,
)
from util.core.orm.models import Device
from util.logger import get_logger
from util.util import extract_device_name

logger = get_logger(__name__)


firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)


@yaspin("Deleting all data from Firebase...")
def delete_all_by_nodes():
    ref = db.reference("/")
    top_level_nodes = ref.get(shallow=True)
    if not top_level_nodes:
        logger.info(f"No data found in Firebase.")
    else:
        for key in top_level_nodes.keys():
            if key != FIREBASE_STATISTICS_NODE:
                logger.info(f"Deleting node: {key}")
                ref.child(key).delete()
        logger.info(f"Deleted all data from Firebase.")


@yaspin("Downloading all data from Firebase...")
def download_all() -> dict:
    ref = db.reference("/")
    top_level_nodes = ref.get(shallow=True)
    device_data = defaultdict(list)

    if not top_level_nodes:
        logger.info(f"No data found in Firebase.")
    else:
        for key in top_level_nodes.keys():
            if key != FIREBASE_STATISTICS_NODE:
                device = extract_device_name(key)
                if Device(device) in Device.__members__.values():
                    node_data = ref.child(key).get()
                    # data = node_data.get("data", {})
                    device_data[device].append(node_data)
        logger.info(f"Downloaded all data from Firebase.")

    return device_data
