import subprocess
import sys
import threading
import time
from http.client import HTTPException
from urllib.error import HTTPError

from scapy.layers.dot11 import Dot11ProbeReq
from scapy.sendrecv import AsyncSniffer
from yaspin import yaspin

import collector.wlan.helpers as wifi_helpers
from collector.core.firebase.helpers import update_device_status
from collector.settings import CHANNEL_HOP_INTERVAL, CHANNELS, FIREBASE_TIMEOUT_STATUS
from collector.wlan.helpers import channel_hopper, check_interface_mode
from collector.wlan.parser import parse_ip_packet
from util.logger import get_logger

logger = get_logger(__name__)


@yaspin(text="Capturing Probe Requests...")
def capture_traffic():
    """
    Captures Wi-Fi traffic and publishes SSIDs and other information.
    """
    sniffer = AsyncSniffer(
        iface=f"{wifi_helpers.INTERFACE}",
        prn=parse_ip_packet,
        store=False,
        filter="type mgt subtype probe-req",
        lfilter=lambda p: p.haslayer(Dot11ProbeReq),
    )
    sniffer.start()
    sniffer.join()


def send_status():
    """
    Updates device status by adding a new timestamp to Firebase Realtime DB.
    """
    while True:
        try:
            update_device_status()
            time.sleep(FIREBASE_TIMEOUT_STATUS)
        except Exception as e:
            logger.error(f"Firebase device status update failed: {str(e)}")


def start(interface: str = None, channel_hopping: bool = False):
    if not check_interface_mode(interface) and not channel_hopping:
        logger.warning("Failed to start the sniffer due to missing monitor interface.")
        # Force reboot if there is no monitor mode (see #1 for more info)
        logger.info("Force reboot of the RPi device.")
        subprocess.run(["sudo", "reboot"])

    status_thread = threading.Thread(target=send_status, daemon=False)
    status_thread.start()

    if channel_hopping:
        channel_hopper_thread = threading.Thread(
            target=channel_hopper,
            args=(wifi_helpers.INTERFACE, CHANNEL_HOP_INTERVAL, CHANNELS),
            daemon=True,
        )
        channel_hopper_thread.start()

        logger.info("Channel hopping enabled via CLI flag.")
        logger.info(
            f"Started channel hopper thread for `{wifi_helpers.INTERFACE}` with {CHANNEL_HOP_INTERVAL * 1000} ms interval.",
        )
    else:
        logger.info("Channel hopping disabled via CLI flag.")

    while True:
        try:
            logger.info("Start capturing packets from Wi-Fi traffic.")
            # Capture the Wi-Fi packets.
            capture_traffic()
        except (HTTPException, HTTPError) as e:
            logger.error(f"HTTP Exception: {str(e)}")
        except KeyboardInterrupt:
            logger.warning("Sniffer stopped forcefully.")
            # 130 - Script terminated by Control-C
            sys.exit(130)
        except Exception as e:
            logger.error(str(e))
        finally:
            logger.info("Sniffer has been stopped.")

        logger.info("Starting the sniffer again.")


if __name__ == "__main__":
    start()
