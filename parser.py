import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from firebase_admin import db
from scapy.layers.dot11 import Dot11ProbeReq

from settings import FIREBASE_NODE, TIMESTAMP_FORMAT, TIMEZONE
from util import is_working_hours


def parse_ip_packet(packet):
    """
    Filters the packet and broadcasts sniffed data (MAC + SSID + timestamp) through a Firebase Realtime DB.
    """
    # Only capture data between 7 AM and 6 PM
    if not is_working_hours():
        return
    # Filter only Probe Request and ignore Probe Requests with wildcard in the SSID field.
    if packet.haslayer(Dot11ProbeReq):
        ssid = None
        try:
            ssid = packet.info.decode("utf-8")
        except UnicodeDecodeError:
            pass
        if ssid:
            # Prepare data record
            data = {
                "mac": packet.addr2,
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
