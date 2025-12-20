import json
import re

from tqdm import tqdm
from yaspin import yaspin

from aggregator.core.orm.helpers import import_data
from aggregator.settings import RSA_KEY_PATH
from util.util import decrypt_data, load_rsa_key_from_file

from . import logger


def extract_device_name(node_key: str) -> str:
    """
    Extracts device name from a Firebase node key by stripping the trailing date.
    Example: "RPI-1-2025-10-31" → "RPI-1"
    """
    match = re.match(r"^(.*)-\d{4}-\d{2}-\d{2}$", node_key)
    if not match:
        raise AttributeError(f"Node key '{node_key}' is not a valid Firebase node key.")
    return match.group(1)


def clean_string(s: str) -> str:
    # Remove NULL and control characters, but keep UTF-8 characters
    return re.sub(r"[\x00-\x1F\x7F-\x9F]", "", s)


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
                record["ssid"] = clean_string(record["ssid"])
                record["mac"] = decrypt_data(rsa_key, record.get("mac"))
                record["device"] = file_name[:5]
                data.append(record)

        import_data(data, False)
    except Exception as e:
        logger.error(
            f"An error occurred during data import from a file '{file_name}'. - {str(e)}"
        )
