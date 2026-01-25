import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from firebase_admin import db
from scapy.layers.dot11 import Dot11ProbeReq

from util.logger import get_logger
from util.util import encrypt_data, is_working_hours, load_rsa_key_from_file

from .settings import (
    FIREBASE_NODE,
    MAC_FILTER,
    RSA_KEY_PATH,
    SSID_FILTER,
    TIMESTAMP_FORMAT,
    TIMEZONE,
)

logger = get_logger(__name__)

RSA_KEY = load_rsa_key_from_file(RSA_KEY_PATH)


def parse_ip_packet(packet):
    """
    Filters the packet and broadcasts sniffed data (MAC + SSID + timestamp) through a Firebase Realtime DB.
    """
    # Only capture data between 7 AM and 6 PM.
    if not is_working_hours(TIMEZONE):
        return
    # Filter only Probe Request.
    if packet.haslayer(Dot11ProbeReq):
        ssid = None
        try:
            ssid = packet.info.decode("utf-8")
        except UnicodeDecodeError:
            pass
        if ssid not in SSID_FILTER and packet.addr2 not in MAC_FILTER:
            # Prepare data record
            data = {
                "mac": encrypt_data(RSA_KEY, packet.addr2),
                "ssid": "*" if not ssid else ssid,
                "timestamp": datetime.fromtimestamp(
                    float(packet.time), tz=ZoneInfo(TIMEZONE)
                ).strftime(TIMESTAMP_FORMAT)[:-3],
            }

            today = datetime.now().strftime(TIMESTAMP_FORMAT.split(" ")[0])
            # Send to Firebase DB
            try:
                db.reference(f"/{FIREBASE_NODE}-{today}/data").push(data)
            except Exception as e:
                logger.error(f"Firebase update failed: {str(e)}")

            # Save locally for backup
            try:
                with open(
                    os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), f"{today}-data.json"
                    ),
                    "a",
                    encoding="utf-8",
                ) as f:
                    f.write(json.dumps(data) + "\n")
            except Exception as e:
                logger.error(f"Local JSON append failed: {str(e)}")
