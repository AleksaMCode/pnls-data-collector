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


@yaspin("Deleting Firebase data by smallest nodes...")
def delete_all_by_smallest_nodes():
    """
    Deletes Firebase data leaf-by-leaf (smallest possible nodes) to avoid
    oversized delete requests on large subtrees.
    """
    root_ref = db.reference("/")
    top_level_nodes = root_ref.get(shallow=True)

    if not top_level_nodes:
        logger.info(f"No data found in Firebase.")
        return

    deleted_nodes = 0

    def _delete_leaf_nodes(path: str):
        nonlocal deleted_nodes
        current_ref = db.reference(path)
        children = current_ref.get(shallow=True)

        if isinstance(children, dict) and children:
            for child_key in children.keys():
                child_path = f"{path.rstrip('/')}/{child_key}"
                _delete_leaf_nodes(child_path)
            return

        current_ref.delete()
        deleted_nodes += 1

    for key in top_level_nodes.keys():
        if key == FIREBASE_STATISTICS_NODE:
            continue
        _delete_leaf_nodes(f"/{key}")

    logger.info(f"Deleted {deleted_nodes} smallest Firebase nodes.")


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
                device_member = next(
                    (
                        member
                        for member in Device.__members__.values()
                        if member.value == device
                    ),
                    None,
                )
                if device_member is not None:
                    node_data = ref.child(key).get()
                    # data = node_data.get("data", {})
                    device_data[device_member.value].append(node_data)
        logger.info(f"Downloaded all data from Firebase.")

    return device_data
