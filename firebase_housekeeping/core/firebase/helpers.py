import logging
from collections import defaultdict

import firebase_admin
from firebase_admin import credentials, db
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential
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


@yaspin("Deleting Firebase data by entry nodes...")
@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=30, max=90),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def delete_all_by_entry_nodes():
    """
    Deletes data at an intermediate level:
    - iterate top-level device/date nodes
    - inspect each direct child (e.g. "data")
    - delete that child's direct children (entry/random-key nodes)
    This avoids deleting a huge top-level subtree in one request and also avoids very deep leaf-by-leaf traversal.
    """
    root_ref = db.reference("/")
    top_level_nodes = root_ref.get(shallow=True)

    if not top_level_nodes:
        logger.info(f"No data found in Firebase.")
        return

    deleted_nodes = 0

    for top_key in top_level_nodes.keys():
        if top_key == FIREBASE_STATISTICS_NODE:
            continue

        top_path = f"/{top_key}"
        second_level = db.reference(top_path).get(shallow=True)

        if not isinstance(second_level, dict) or not second_level:
            db.reference(top_path).delete()
            deleted_nodes += 1
            continue

        for second_key in second_level.keys():
            second_path = f"{top_path}/{second_key}"
            entry_nodes = db.reference(second_path).get(shallow=True)

            try:
                db.reference(second_path).delete()
                logging.info(f"Bulk delete successful for '{second_path}")
                deleted_nodes += 1
                continue
            except Exception as e:
                logger.warning(
                    f"Bulk delete failed for '{second_path}'. Falling back to entry-level delete. Error: {e}"
                )
            try:
                if isinstance(entry_nodes, dict) and entry_nodes:
                    for entry_key in entry_nodes.keys():
                        db.reference(f"{second_path}/{entry_key}").delete()
                        deleted_nodes += 1
                else:
                    db.reference(second_path).delete()
                    deleted_nodes += 1
            except Exception as e:
                logger.warning(
                    f"Fallback for entry-level delete failed for '{second_path}'. Error: {e}"
                )
                raise

    logger.info(f"Deleted {deleted_nodes} Firebase entry nodes.")


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
