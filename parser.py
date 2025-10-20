import json
from datetime import datetime

from firebase_admin import db
from scapy.layers.dot11 import Dot11ProbeReq

from settings import FIREBASE_NODE, TIMESTAMP_FORMAT


def parse_ip_packet(packet):
    """
    Filters the packet and broadcasts sniffed data (SSID + timestamp) through a websocket.
    """
    # TODO add time checker here - only capture data between 7 AM and 6 PM
    # Filter only Probe Request and ignore Probe Requests with wildcard in the SSID field.
    if packet.haslayer(Dot11ProbeReq):
        ssid = None
        try:
            ssid = packet.info.decode("utf-8")
            # Test what info is in packet! TODO remove this print after testing
            # TODO how to get fields_desc ?
            print(packet.network_stats())
        except UnicodeDecodeError:
            pass
        if ssid:
            # Prepare data record
            data = {
                "ssid": ssid,
                "timestamp": datetime.utcfromtimestamp(float(packet.time)).strftime(
                    TIMESTAMP_FORMAT
                )[:-3],
                # TODO add MAC address
            }

            # Send to Firebase DB
            try:
                db.reference(f"/{FIREBASE_NODE}/data").update(data)
            except Exception as e:
                print(f"Firebase update failed: {e}")

            # Save locally
            try:
                with open("data.json", "a", encoding="utf-8") as f:
                    f.write(json.dumps(data) + "\n")
            except Exception as e:
                print(f"Local JSON append failed: {e}")
