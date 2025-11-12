import subprocess
import sys
import threading
from http.client import HTTPException
from urllib.error import HTTPError

import firebase_admin
from firebase_admin import credentials
from scapy.sendrecv import AsyncSniffer
from yaspin import yaspin

from .parser import parse_ip_packet
from .settings import FIREBASE_CREDENTIALS, FIREBASE_DB_URL, INTERFACES
from .sniffer_status import send_status

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
        for interface in [f"{default_interface}mon", default_interface]:
            try:
                interface_info = subprocess.run(
                    ["iwconfig", interface], capture_output=True, text=True
                ).stdout

                if "Mode:" in interface_info:
                    # Parse out only the interface mode.
                    interface_mode = interface_info.split("Mode:", 1)[1].split(" ", 1)[
                        0
                    ]
                    if interface_mode.strip() == "Monitor":
                        INTERFACE = interface
                        return True
                    else:
                        print(f"Interface `{interface}` not in Monitor mode.")
            except:
                print("An Exception occurred during checking interface mode.")

    return False


def start():
    if not check_interface_mode():
        print("Failed to start the sniffer due to missing monitor interface.")
        # Force reboot if there is no monitor mode (see #1 for more info)
        subprocess.run(["sudo", "reboot"])

    status_thread = threading.Thread(target=send_status, daemon=False)
    status_thread.start()

    while True:
        try:
            print("Capture packets from Wi-Fi traffic.")
            # Capture the Wi-Fi packets.
            capture_traffic(status_thread)
        except (HTTPException, HTTPError) as e:
            print(f"HTTP Exception: {str(e)}")
        except KeyboardInterrupt as e:
            print("Sniffer stopped forcefully.")
            # 130 - Script terminated by Control-C
            sys.exit(130)
        except Exception as e:
            print(str(e))
        finally:
            print("Sniffer has been stopped.")

        print("Starting the sniffer again.")


if __name__ == "__main__":
    start()
