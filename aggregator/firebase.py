from datetime import date, datetime

from firebase_admin import db

from core.orm.models import Device
from settings import TIMESTAMP_FORMAT
from util import extract_device_name


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
                    "mac": entry_value.get("mac"),
                    "ssid": entry_value.get("ssid"),
                    "timestamp": entry_value.get("timestamp"),
                }
            )

    return results
