from datetime import date, datetime
from zoneinfo import ZoneInfo

from firebase_admin import db
from tenacity import retry, stop_after_attempt, wait_random
from yaspin import yaspin

from aggregator.core.orm.helpers import (
    get_total_captured_info_count,
    get_total_captured_mac_count,
    get_total_captured_ssid_count,
)
from aggregator.core.orm.models import Device
from util.util import decrypt_data, load_rsa_key_from_file

from .settings import RSA_KEY_PATH, TIMESTAMP_FORMAT, TIMEZONE
from .util import extract_device_name

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
    ref = db.reference("/")
    data = ref.get()

    if not data:
        print("No data found in Firebase.")
        return []

    today = date.today()
    results = []

    for node_key, node_value in data.items():
        data_entries = node_value.get("data", {})
        for entry_key, entry_value in data_entries.items():
            ts_str = entry_value.get("timestamp")
            ts = datetime.strptime(ts_str, TIMESTAMP_FORMAT).date()

            if start_date <= ts <= today:
                results.append(
                    {
                        "device": extract_device_name(node_key),
                        "mac": entry_value.get("mac"),
                        "ssid": entry_value.get("ssid"),
                        "timestamp": ts_str,
                    }
                )

    return results


@yaspin(text="Fetching data from Firebase...")
def fetch_data(target_date: date):
    """
    Fetch data from Firebase only for specific device-date nodes for `target_date`.
    Returns a list of entries.
    """
    results = []

    for device in Device:
        try:
            # e.g. "RPI-1-2025-10-31"
            node_key = (
            f"{device.value}-{target_date.strftime(TIMESTAMP_FORMAT.split(' ')[0])}"
        )
            node_value = fetch_firebase_node(node_key)
            if not node_value:
                continue
        except Exception as e:
            print(f"Firebase exception occurred: {e}")

        data_entries = node_value.get("data", {})
        for entry_value in data_entries.values():
            results.append(
                {
                    "device": device.value,
                    "mac": decrypt_data(RSA_KEY, entry_value.get("mac")),
                    "ssid": entry_value.get("ssid"),
                    "timestamp": entry_value.get("timestamp"),
                }
            )

    return results


@yaspin(text="Publishing stats data to Firebase...")
def publish_stats_data():
    """
    Publishes key statistics to Firebase.
    """
    node = "stats"
    timestamp = datetime.now(ZoneInfo(TIMEZONE)).strftime(TIMESTAMP_FORMAT)

    stats = {
        "total_count": get_total_captured_info_count(),
        "mac_count": get_total_captured_mac_count(),
        "ssid_count": get_total_captured_ssid_count(),
    }

    try:
        for key, count in stats.items():
            db.reference(f"/{node}/{key}").update(
                {"count": count, "timestamp": timestamp}
            )
        print(f"Published stats data to Firebase")
    except Exception as e:
        print(f"Publishing stats data to Firebase failed: {e}")
