import json
import os
import re
from datetime import date

from aggregator.core.orm.models import Country, IEEERegistry
from util.mattermost.helpers import send_webhook_message
from util.util import decrypt_data, load_rsa_key_from_file

# Fix for pipeline. See #38
if os.getenv("ENV") != "test":
    from tqdm import tqdm
    from geopy import Nominatim
    from aggregator.settings import RSA_KEY_PATH, SLACK_WEBHOOK_URL

from . import logger


def clean_string(s: str) -> str:
    # Remove NULL and control characters, but keep UTF-8 characters
    return re.sub(r"[\x00-\x1F\x7F-\x9F]", "", s)


def parse_data_local(file_name):
    """
    Parse device local data.
    The filename should be in a specific format - e.g. RPI-1*.json.
    """
    logger.info("Starting import of local data from device.")
    # Added another RSA_KEY here to avoid circular import. Good enough for now.
    # TODO Maybe fix this another way #techdebt
    rsa_key = load_rsa_key_from_file(RSA_KEY_PATH)
    data = []
    try:
        with open(file_name, "r") as file:
            for record in tqdm(file, desc="Importing records", unit="record"):
                record = json.loads(record.strip())
                record["ssid"] = clean_string(record["ssid"])
                record["mac"] = decrypt_data(rsa_key, record.get("mac"))
                record["device"] = file_name[:5]
                data.append(record)

        return data
    except Exception as e:
        logger.error(
            f"An error occurred during data import from a file '{file_name}'. - {str(e)}"
        )


def get_country_id(session, address, user_agent="*"):
    """
    Use geopy to geocode the address and return country id from the DB.
    """
    # Geopy uses `nominatim.openstreetmap.org`; use sleep when calling this function as the API has rate limit.
    # TODO test this before using!!
    geolocator = Nominatim(user_agent=user_agent)
    try:
        location = geolocator.geocode(address, language="en")
        if location and location.raw.get("address"):
            country_name = location.raw["address"].get("country")
            if country_name:
                country = (
                    session.query(Country).filter_by(name=country_name).one_or_none()
                )
                return country.id if country else None
    except Exception as e:
        logger.error(f"Geocoding error for '{address}': {e}")
    return None


def mac_normalize(mac: str) -> str:
    return mac.replace(":", "").upper()


def mac_to_oui_candidates(mac: str):
    mac_normalized = mac_normalize(mac)

    return {
        IEEERegistry.MA_S: mac_normalized[:9],  # 36 bits
        IEEERegistry.MA_M: mac_normalized[:7],  # 28 bits
        IEEERegistry.MA_L: mac_normalized[:6],  # 24 bits
    }


def publish_to_channel(data: dict, probe_req_count: int, import_date: date = None):
    # This is tightly coupled with stats data from firebase#publish_stats_data.
    first_line = (
        "**Today's data has been aggregated.**\n"
        if not import_date
        else f"**Data imported for date '{import_date}'.**\n"
    )

    mattermost_msg = (
        first_line
        + f"(Captured Probe Requests: **{probe_req_count:,}**)\n"
        + f"* Total captured probe requests: {data['total_count']:,}\n"
        + f"* Total captured unique MAC addresses: {data['mac_count']:,}\n"
        + f"* Total captured unique SSIDs: {data['ssid_count']:,}\n"
    )
    send_webhook_message(mattermost_msg, webhook=SLACK_WEBHOOK_URL)
