import base64
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from typing_extensions import deprecated


def is_working_hours(tz="Europe/Paris"):
    """
    Returns True if the current time is between 7 AM and 6 PM.
    """
    now = datetime.now(ZoneInfo(tz)).time()
    return time(7, 0) <= now <= time(18, 0)


@deprecated("This is no longer used as part of the aggregator import")
def is_after_six(tz="Europe/Paris"):
    """
    Returns True if the current time after 6 PM.
    """
    now = datetime.now(ZoneInfo(tz)).time()
    return now > time(18, 0)


def load_rsa_key_from_file(rsa_key):
    """
    Return load private or public RSA key.
    """
    with open(rsa_key, "rb") as f:
        return RSA.import_key(f.read())


def encrypt_data(public_key, data: str):
    cipher = PKCS1_OAEP.new(public_key)
    encrypted_data = cipher.encrypt(data.encode("utf-8"))
    return base64_encode(encrypted_data)


def decrypt_data(private_key, encrypted_data: str):
    cipher = PKCS1_OAEP.new(private_key)
    decrypted_data = cipher.decrypt(base64_decode(encrypted_data))
    return decrypted_data.decode("utf-8")


def base64_encode(data):
    return base64.b64encode(data).decode("utf-8")


def base64_decode(data: str):
    return base64.b64decode(data)


def extract_device_name(node_key: str) -> str:
    """
    Extracts device name from a Firebase node key by stripping the trailing date.
    Example: "RPI-1-2025-10-31" → "RPI-1"
    """
    match = re.match(r"^(.*)-\d{4}-\d{2}-\d{2}$", node_key)
    if not match:
        raise AttributeError(f"Node key '{node_key}' is not a valid Firebase node key.")
    return match.group(1)
