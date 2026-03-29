import subprocess
import sys
import threading
from http.client import HTTPException
from urllib.error import HTTPError

import firebase_admin
from firebase_admin import credentials
from scapy.sendrecv import AsyncSniffer
from yaspin import yaspin

from util.logger import get_logger

from .parser import parse_ip_packet
from .settings import FIREBASE_CREDENTIALS, FIREBASE_DB_URL, INTERFACES
from .sniffer_status import send_status

logger = get_logger(__name__)

INTERFACE = ""

# Init Firebase DB
firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)


@yaspin(text="Capturing Probe Requests...")
def capture_traffic(status_thread: threading.Thread):
    """
    Captures Wi-Fi traffic and publish SSIDs and other information.
    """
    sniffer = AsyncSniffer(
        iface=f"{INTERFACE}",
        prn=parse_ip_packet,
        store=False,
    )
    sniffer.start()
    sniffer.join()
    status_thread.join()


@yaspin(text="Checking interface mode...")
def check_interface_mode():
    """
    Checks if the wireless interface has been set to the Monitor mode.
    """
    global INTERFACE
    for default_interface in INTERFACES:
        # Changed for #213
        interface = f"{default_interface}mon"
        try:
            interface_info = subprocess.run(
                ["iwconfig", interface], capture_output=True, text=True
            ).stdout

            if "Mode:" in interface_info:
                # Parse out only the interface mode.
                interface_mode = interface_info.split("Mode:", 1)[1].split(" ", 1)[0]
                if interface_mode.strip() == "Monitor":
                    INTERFACE = interface
                    logger.info(f"Interface `{interface}` is in Monitor mode.")
                    return True
                else:
                    logger.warning(f"Interface `{interface}` not in Monitor mode.")
        except Exception as e:
            logger.error(
                f"An Exception occurred during checking interface mode - {str(e)}"
            )

    return False


def start():
    if not check_interface_mode():
        logger.warning("Failed to start the sniffer due to missing monitor interface.")
        # Force reboot if there is no monitor mode (see #1 for more info)
        logger.info("Force reboot of the RPi device.")
        subprocess.run(["sudo", "reboot"])

    status_thread = threading.Thread(target=send_status, daemon=False)
    status_thread.start()

    while True:
        try:
            logger.info("Start capturing packets from Wi-Fi traffic.")
            # Capture the Wi-Fi packets.
            capture_traffic(status_thread)
        except (HTTPException, HTTPError) as e:
            logger.error(f"HTTP Exception: {str(e)}")
        except KeyboardInterrupt as e:
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
