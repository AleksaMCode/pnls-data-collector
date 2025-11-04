import base64
from datetime import datetime, time
from zoneinfo import ZoneInfo

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from settings import TIMEZONE


def is_working_hours(tz=TIMEZONE):
    """
    Returns True if the current time is between 7 AM and 6 PM.
    """
    now = datetime.now(ZoneInfo(tz)).time()
    return time(7, 0) <= now <= time(18, 0)


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
