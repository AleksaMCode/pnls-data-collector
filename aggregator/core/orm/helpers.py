import json
from datetime import datetime

from sqlalchemy import desc, func
from tqdm import tqdm
from yaspin import yaspin

from aggregator import settings, util
from util.logger import get_logger
from util.util import decrypt_data, load_rsa_key_from_file

from ...settings import RSA_KEY_PATH
from ...util import util
from . import _session
from .models import MAC, SSID, CapturedInfo, ImportsInfo, LocationMapping

logger = get_logger(__name__)


def get_latest_import_date():
    logger.info("Getting latest import date from the DB.")
    with _session() as db:
        return (
            db.query(ImportsInfo)
            .order_by(desc(ImportsInfo.timestamp))
            .first()
            .timestamp
        )


def get_total_captured_info_count():
    logger.info("Getting total captured info count from the DB.")
    with _session() as db:
        return db.query(func.sum(ImportsInfo.captured)).scalar()


def get_total_captured_mac_count():
    logger.info("Getting total captured mac count from the DB.")
    with _session() as db:
        return db.query(func.count(MAC.id)).scalar()


def get_total_captured_ssid_count():
    logger.info("Getting total captured ssid count from the DB.")
    with _session() as db:
        return db.query(func.count(SSID.id)).scalar()


@yaspin(text="Importing data from Firebase to local database...")
def import_data(data, firebase_import: bool = True):
    logger.info("Starting import of data from Firebase to local database.")
    with _session() as db:
        try:
            # Cache existing SSIDs and MACs for fast lookup
            ssid_map = {s.ssid: s.id for s in db.query(SSID).all()}
            mac_map = {m.mac: m.id for m in db.query(MAC).all()}

            captured_records = []
            for record in tqdm(data, desc="Importing records", unit="record"):
                device_name = record.get("device")
                ssid_str = util.clean_string(record.get("ssid"))
                mac_str = record.get("mac")

                if mac_str in settings.MAC_FILTER:
                    continue

                timestamp_str = record.get("timestamp")

                if not ssid_str or not mac_str or not timestamp_str:
                    continue

                ts = datetime.strptime(timestamp_str, settings.TIMESTAMP_FORMAT)

                ssid_id = ssid_map.get(ssid_str)
                if not ssid_id:
                    ssid_obj = SSID(ssid=ssid_str)
                    db.add(ssid_obj)
                    db.flush()
                    ssid_map[ssid_str] = ssid_obj.id
                    ssid_id = ssid_obj.id

                mac_id = mac_map.get(mac_str)
                if not mac_id:
                    mac_obj = MAC(mac=mac_str)
                    db.add(mac_obj)
                    db.flush()
                    mac_map[mac_str] = mac_obj.id
                    mac_id = mac_obj.id

                mapping = (
                    db.query(LocationMapping).filter_by(device=device_name).first()
                )
                if not mapping:
                    logger.warning(
                        f"No location mapping found for device {device_name}, skipping record."
                    )
                    continue

                location_id = mapping.location_id
                captured_records.append(
                    CapturedInfo(
                        ssid=ssid_id, mac=mac_id, location=location_id, timestamp=ts
                    )
                )
        except Exception as e:
            db.rollback()
            logger.error(f"Error occurred during data import - {str(e)}")
            return

        if captured_records:
            db.add_all(captured_records)
            # Only update stats when importing from Firebase.
            # For import of local data manually update stats.
            # TODO Maybe fix this (automate stats update) in the future #techdebt
            if firebase_import:
                db.add(ImportsInfo(captured=len(captured_records)))
            try:
                db.commit()
                logger.info(f"Imported {len(captured_records)} new captured records.")
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to add new captured records - {str(e)}")


@yaspin(text="Importing data from device to local database...")
def import_data_local(file_name):
    """
    Import of device local data to local database.
    The filename should be in a specific format - e.g. RPI-1*.json.
    """
    logger.info("Starting import of local data from device.")
    # Added another RSA_KEY here to avoid circular import. Good enough for now.
    # TODO Maybe fix this another way #techdept
    rsa_key = load_rsa_key_from_file(RSA_KEY_PATH)
    data = []
    try:
        with open(file_name, "r") as file:
            for record in tqdm(file, desc="Importing records", unit="record"):
                record = json.loads(record.strip())
                record["ssid"] = util.clean_string(record["ssid"])
                record["mac"] = decrypt_data(rsa_key, record.get("mac"))
                record["device"] = file_name[:5]
                data.append(record)
    except Exception as e:
        logger.error(f"An error occurred during data import from a file '{file_name}'. - {str(e)}")

    import_data(data, False)
