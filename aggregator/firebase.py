from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from firebase_admin import db
from tenacity import retry, stop_after_attempt, wait_random
from tqdm import tqdm
from yaspin import yaspin

from aggregator.core.orm.helpers import (
    get_total_captured_info_count,
    get_total_captured_mac_count,
    get_total_captured_ssid_count,
)
from aggregator.core.orm.models import Device
from util.logger import get_logger
from util.util import decrypt_data, load_rsa_key_from_file

from .mattermost import publish_to_channel
from .settings import FIREBASE_STATISTICS_NODE, RSA_KEY_PATH, TIMESTAMP_FORMAT, TIMEZONE
from .util.util import extract_device_name

logger = get_logger(__name__)

RSA_KEY = load_rsa_key_from_file(RSA_KEY_PATH)


@retry(stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
def fetch_firebase_node(node: str):
    ref = db.reference("/")
    return ref.child(node).get()


@yaspin(text="Fetching data from Firebase...")
def fetch_all_data(start_date: date):
    """
    Fetch all data from Firebase Realtime DB from `start_date` up to and including today.
    Returns a list of entries.
    """
    logger.info("Started fetching data from Firebase.")
    ref = db.reference("/")
    data = ref.get()

    if not data:
        logger.info("No data found in Firebase.")
        return []

    today = date.today()
    results = []

    for node_key, node_value in data.items():
        device_name = extract_device_name(node_key)
        data_entries = node_value.get("data", {})
        for entry_key, entry_value in data_entries.items():
            ts_str = entry_value.get("timestamp")
            ts = datetime.strptime(ts_str, TIMESTAMP_FORMAT).date()

            if start_date <= ts <= today:
                results.append(
                    {
                        "device": device_name,
                        "mac": entry_value.get("mac"),
                        "ssid": entry_value.get("ssid"),
                        "timestamp": ts_str,
                    }
                )

    logger.info("Finished fetching data from Firebase.")
    return results


@yaspin(text="Fetching data from Firebase...")
def fetch_data(target_date: date):
    """
    Fetch data from Firebase only for specific device-date nodes for `target_date`.
    Returns a list of entries.
    """
    logger.info("Started fetching data from Firebase.")
    results = []

    for device in Device:
        try:
            # e.g. "RPI-1-2025-10-31"
            node_key = (
                f"{device.value}-{target_date.strftime(TIMESTAMP_FORMAT.split(' ')[0])}"
            )
            node_value = fetch_firebase_node(node_key)
            if not node_value:
                logger.warning(f"No node '{node_key}' found in Firebase DB.")
                continue
        except Exception as e:
            logger.error(f"Firebase exception occurred: {str(e)}")

        data_entries = node_value.get("data", {})
        for entry_value in tqdm(
            data_entries.values(),
            desc=f"Fetching data records for {device.value}",
            unit="record",
        ):
            results.append(
                {
                    "device": device.value,
                    "mac": decrypt_data(RSA_KEY, entry_value.get("mac")),
                    "ssid": entry_value.get("ssid"),
                    "timestamp": entry_value.get("timestamp"),
                }
            )

    logger.info("Finished fetching data from Firebase.")
    return results


@yaspin(text="Publishing stats data to Firebase...")
def publish_stats_data():
    """
    Publishes key statistics to Firebase.
    """
    timestamp = datetime.now(ZoneInfo(TIMEZONE)).strftime(TIMESTAMP_FORMAT)

    stats = {
        "total_count": get_total_captured_info_count(),
        "mac_count": get_total_captured_mac_count(),
        "ssid_count": get_total_captured_ssid_count(),
    }

    try:
        for key, count in stats.items():
            db.reference(f"/{FIREBASE_STATISTICS_NODE}/{key}").update(
                {"count": count, "timestamp": timestamp}
            )
        logger.info(f"Published stats data to Firebase.")
    except Exception as e:
        logger.error(f"Publishing stats data to Firebase failed: {str(e)}")

    # TODO Maybe move this part to another function outside of firebase - in that case this function needs to return data
    # Publish message to Mattermost
    try:
        publish_to_channel(stats)
    except Exception as e:
        logger.error(f"Publishing stats data to Mattermost failed: {str(e)}")


@yaspin("Deleting all data from Firebase...")
def delete_all():
    ref = db.reference("/")
    ref.delete()
    logger.info("Deleted all data from Firebase.")


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


def download_today() -> dict:
    """
    Downloads data from Firebase that was stored today.
    """
    device_data = defaultdict(list)

    for device in Device:
        try:
            # e.g. "RPI-1-2025-10-31"
            node_key = f"{device.value}-{datetime.today().strftime(TIMESTAMP_FORMAT.split(' ')[0])}"
            node_value = fetch_firebase_node(node_key)
            if not node_value:
                continue
        except Exception as e:
            logger.error(f"Firebase exception occurred: {str(e)}")

        data_entries = node_value.get("data", {})
        device_data[device].append(data_entries)

    return device_data


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
