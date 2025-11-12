from datetime import date, datetime

from firebase_admin import db

from aggregator.core.orm.helpers import (
    get_total_captured_info_count,
    get_total_captured_mac_count,
    get_total_captured_ssid_count,
)
from aggregator.core.orm.models import Device
from .settings import TIMESTAMP_FORMAT, RSA_KEY_PATH
from .util import extract_device_name
from util.util import decrypt_data, is_working_hours, load_rsa_key_from_file

RSA_KEY = load_rsa_key_from_file(RSA_KEY_PATH)

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


def fetch_data(target_date: date):
    """
    Fetch data from Firebase only for specific device-date nodes for `target_date`.
    Returns a list of entries.
    """
    ref = db.reference("/")
    results = []

    for device in Device:
        # e.g. "RPI-1-2025-10-31"
        node_key = (
            f"{device.value}-{target_date.strftime(TIMESTAMP_FORMAT.split(' ')[0])}"
        )
        node_value = ref.child(node_key).get()
        if not node_value:
            continue

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

def publish_stats_data():
    node = "stats"
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)

    try:
        db.reference(f"/{node}/total_count").update(
            {
                "count": get_total_captured_info_count(),
                "timestamp": timestamp,
            }
        )
        db.reference(f"/{node}/mac_count").update(
            {
                "count": get_total_captured_mac_count(),
                "timestamp": timestamp,
            }
        )
        db.reference(f"/{node}/ssid_count").update(
            {
                "count": get_total_captured_ssid_count(),
                "timestamp": timestamp,
            }
        )
    except Exception as e:
        print(f"Firebase update failed: {e}")