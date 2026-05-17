from datetime import datetime
from zoneinfo import ZoneInfo

from scapy.layers.dot11 import Dot11ProbeReq

import collector.wlan.helpers as wifi_helpers
from collector.core.firebase.helpers import publish_captured_date
from collector.settings import (
    MAC_FILTER,
    RSA_KEY_PATH,
    SSID_FILTER,
    TIMESTAMP_FORMAT,
    TIMEZONE,
)
from collector.util.util import publish_captured_data_locally
from util.logger import get_logger
from util.util import encrypt_data, is_working_hours, load_rsa_key_from_file

logger = get_logger(__name__)

RSA_KEY = load_rsa_key_from_file(RSA_KEY_PATH)


def parse_ip_packet(packet):
    """
    Filters the packet and broadcasts sniffed data (MAC + SSID + timestamp) through a Firebase Realtime DB.
    """
    # Only capture data between 7 AM and 6 PM.
    if not is_working_hours(TIMEZONE):
        return
    # Filter only Probe Request. This is probably no longer needed due to utilization of filter in AsyncSniffer.
    # This just to safe in case the filter fails.
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
                "channel": wifi_helpers.extract_channel_from_packet(packet)
                or wifi_helpers.WLAN_CHANNEL,
                "timestamp": datetime.fromtimestamp(
                    float(packet.time), tz=ZoneInfo(TIMEZONE)
                ).strftime(TIMESTAMP_FORMAT)[:-3],
            }

            today = datetime.now().strftime(TIMESTAMP_FORMAT.split(" ")[0])
            # Send to Firebase DB
            try:
                publish_captured_date(data, today)
            except Exception as e:
                logger.error(f"Firebase update failed: {str(e)}")

            # Save locally for backup
            try:
                publish_captured_data_locally(data, today)
            except Exception as e:
                logger.error(f"Local JSON append failed: {str(e)}")
