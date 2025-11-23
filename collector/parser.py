import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from firebase_admin import db
from scapy.layers.dot11 import Dot11ProbeReq

from util.util import encrypt_data, is_working_hours, load_rsa_key_from_file

from .settings import (
    FIREBASE_NODE,
    MAC_FILTER,
    RSA_KEY_PATH,
    TIMESTAMP_FORMAT,
    TIMEZONE,
)

RSA_KEY = load_rsa_key_from_file(RSA_KEY_PATH)


def parse_ip_packet(packet):
    """
    Filters the packet and broadcasts sniffed data (MAC + SSID + timestamp) through a Firebase Realtime DB.
    """
    # Only capture data between 7 AM and 6 PM
    if not is_working_hours(TIMEZONE):
        return
    # Filter only Probe Request and ignore Probe Requests with wildcard in the SSID field.
    if packet.haslayer(Dot11ProbeReq):
        ssid = None
        try:
            ssid = packet.info.decode("utf-8")
        except UnicodeDecodeError:
            pass
        if ssid and packet.addr2 not in MAC_FILTER:
            # Prepare data record
            data = {
                "mac": encrypt_data(RSA_KEY, packet.addr2),
                "ssid": ssid,
                "timestamp": datetime.fromtimestamp(
                    float(packet.time), tz=ZoneInfo(TIMEZONE)
                ).strftime(TIMESTAMP_FORMAT)[:-3],
            }

            # Send to Firebase DB
            try:
                db.reference(
                    f"/{FIREBASE_NODE}-{datetime.now().strftime(TIMESTAMP_FORMAT.split(' ')[0])}/data"
                ).push(data)
            except Exception as e:
                print(f"Firebase update failed: {e}")

            # Save locally for backup
            try:
                with open(
                    os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), "data.json"
                    ),
                    "a",
                    encoding="utf-8",
                ) as f:
                    f.write(json.dumps(data) + "\n")
            except Exception as e:
                print(f"Local JSON append failed: {e}")
