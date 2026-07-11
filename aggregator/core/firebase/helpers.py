from collections import defaultdict
from datetime import date, datetime
from warnings import deprecated
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials, db
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from yaspin import yaspin

from aggregator.core.orm.helpers import (
    get_all_data_from_company_capture_summary,
    get_all_data_from_company_capture_summary_by_device,
    get_all_data_from_location_mapping_resolved,
    get_device_total_captured_data,
    get_today_data_from_daily_captured_stats_per_device,
    get_total_captured_info_count,
    get_total_captured_mac_count,
    get_total_captured_ssid_count,
)
from aggregator.core.orm.models import DailyCapturedPerDevice
from aggregator.settings import (
    FIREBASE_CREDENTIALS,
    FIREBASE_DB_URL,
    FIREBASE_STATISTICS_NODE,
    RSA_KEY_PATH,
    TIMESTAMP_FORMAT,
    TIMEZONE,
)
from util.core.orm.models import Device
from util.logger import get_logger
from util.util import decrypt_data, extract_device_name, load_rsa_key_from_file

logger = get_logger(__name__)

RSA_KEY = load_rsa_key_from_file(RSA_KEY_PATH)

firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)


@retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=30, max=90))
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
    Returns a list of entries (probe requests) captured on all the devices.
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
            msg = f"Failed to fetch data from Firebase for device `{device.value}` (node {node_key})."
            logger.warning(msg)
            raise Exception(f"{msg} Import of Firebase data failed.")

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
                    "channel": entry_value.get("channel"),
                    "timestamp": entry_value.get("timestamp"),
                }
            )

    logger.info("Finished fetching data from Firebase.")
    return results


@yaspin(text="Publishing daily stats data to Firebase...")
def publish_daily_stats_data(data: list[DailyCapturedPerDevice]):
    for capture in tqdm(data, desc="Importing stats capture records", unit="record"):
        publish_daily_stats_capture_data(capture)
    logger.info("Finished publishing daily stats data.")


def publish_daily_stats_capture_data(capture: DailyCapturedPerDevice):
    db.reference(
        f"/{FIREBASE_STATISTICS_NODE}/daily/{capture.date}/{capture.device}"
    ).update(
        {
            "ssid": capture.ssid,
            "mac": capture.mac,
            "probe_requests": capture.probe_request,
        }
    )


@deprecated("This is no longer used as this data is published to Supabase.")
@yaspin(text="Publishing stats data to Firebase...")
def publish_stats_data(import_date: date | None = None):
    """
    Publishes key statistics to Firebase.
    Returns stats data.
    """
    timestamp = datetime.now(ZoneInfo(TIMEZONE)).strftime(TIMESTAMP_FORMAT)

    stats = {
        "total_count": get_total_captured_info_count(),
        "mac_count": get_total_captured_mac_count(),
        "ssid_count": get_total_captured_ssid_count(),
    }

    daily_stats = get_today_data_from_daily_captured_stats_per_device(
        TIMEZONE, import_date
    )

    try:
        for key, count in stats.items():
            db.reference(f"/{FIREBASE_STATISTICS_NODE}/{key}").update(
                {"count": count, "timestamp": timestamp}
            )
        for capture in daily_stats:
            publish_daily_stats_capture_data(capture)
        logger.info(f"Published stats data to Firebase.")
        return stats
    except Exception as e:
        logger.error(f"Publishing stats data to Firebase failed: {str(e)}")


@deprecated("This is no longer used as this data is published to Supabase.")
@yaspin(text="Publishing manufacturers data to Firebase...")
def publish_manufacturers_data():
    manufacturer_data = get_all_data_from_company_capture_summary()

    try:
        for manufacturer in manufacturer_data:
            key = manufacturer.company
            # From docs: https://firebase.google.com/docs/database/admin/structure-data#how_data_is_structured_its_a_json_tree
            for invalid_char in [".", "$", "#", "[", "]", "/"]:
                key = key.replace(invalid_char, " ")

            db.reference(f"/{FIREBASE_STATISTICS_NODE}/manufacturers/{key}").update(
                {
                    "country": manufacturer.country_alpha3,
                    "count": manufacturer.total_occurrences,
                    "percentage": manufacturer.percentage,
                }
            )
        logger.info("Published manufacturers data to Firebase.")
    except Exception as e:
        logger.error(f"Publishing manufacturers data to Firebase failed: {str(e)}")


@deprecated("This is no longer used as this data is published to Supabase.")
@yaspin(text="Publishing device location data to Firebase...")
def publish_devices_data():
    device_data = get_all_data_from_location_mapping_resolved()

    try:
        for device_info in device_data:
            device = device_info.device
            totals = get_device_total_captured_data(Device(device))

            db.reference(f"/{FIREBASE_STATISTICS_NODE}/devices/{device}").update(
                {
                    "location": device_info.location,
                    "coordinates": device_info.coordinates,
                    "ssid": totals.ssid,
                    "probes": totals.probe_request,
                    "mac": totals.mac,
                }
            )
        logger.info("Published devices data to Firebase.")
    except Exception as e:
        logger.error(f"Publishing devices data to Firebase failed: {str(e)}")


@deprecated("This is no longer used as this data is published to Supabase.")
@yaspin(text="Publishing sankey data to Firebase...")
def publish_sankey_data():
    try:
        for device in Device:
            manufacturer_data = get_all_data_from_company_capture_summary_by_device(
                device
            )

            for manufacturer in manufacturer_data:
                key = manufacturer.company
                # From docs: https://firebase.google.com/docs/database/admin/structure-data#how_data_is_structured_its_a_json_tree
                for invalid_char in [".", "$", "#", "[", "]", "/"]:
                    key = key.replace(invalid_char, " ")

                db.reference(
                    f"/{FIREBASE_STATISTICS_NODE}/sankey/{device.value}/{key}"
                ).update(
                    {
                        "country": manufacturer.country_alpha3,
                    }
                )

        logger.info("Published sankey data to Firebase.")
    except Exception as e:
        logger.error(f"Publishing sankey data to Firebase failed: {str(e)}")


@yaspin("Deleting all data from Firebase...")
def delete_all():
    ref = db.reference("/")
    ref.delete()
    logger.info("Deleted all data from Firebase.")


@yaspin("Deleting all stats data from Firebase...")
def delete_stats():
    ref = db.reference("/stats")
    ref.delete()
    logger.info("Deleted all data from Firebase.")


@yaspin("Deleting manufacturers data from Firebase...")
def delete_manufacturers():
    ref = db.reference(f"/{FIREBASE_STATISTICS_NODE}/manufacturers")
    ref.delete()
    logger.info("Deleted manufacturers data from Firebase.")


@yaspin("Deleting sankey data from Firebase...")
def delete_manufacturers():
    ref = db.reference(f"/{FIREBASE_STATISTICS_NODE}/sankey")
    ref.delete()
    logger.info("Deleted sankey data from Firebase.")


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
