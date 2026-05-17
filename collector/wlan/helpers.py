import os
import subprocess
import time

from scapy.layers.dot11 import Dot11Elt, RadioTap
from yaspin import yaspin

from util.logger import get_logger

# Fix for pipeline. See #10
if os.getenv("ENV") != "test":

    from collector.settings import INTERFACES

INTERFACE = ""
logger = get_logger(__name__)
# Current WLAN Channel for 2.4 GHz range.
WLAN_CHANNEL = 1
FREQ_TO_CHANNEL_24GHZ = {
    2412: 1,
    2417: 2,
    2422: 3,
    2427: 4,
    2432: 5,
    2437: 6,
    2442: 7,
    2447: 8,
    2452: 9,
    2457: 10,
    2462: 11,
    2467: 12,
    2472: 13,
    2484: 14,
}


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


def _set_channel(interface: str, channel: int):
    global WLAN_CHANNEL
    try:
        result = subprocess.run(
            ["iw", "dev", interface, "set", "channel", str(channel)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"Failed to set channel {channel}: {result.stderr}")
        else:
            WLAN_CHANNEL = channel
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to set channel {channel} on {interface}: {e.stderr}")


def extract_channel_from_packet(packet):
    """
    Extracts the 2.4 GHz WLAN channel directly from packet metadata.
    """
    # Radiotap is a metadata header the capture interface/driver adds to each sniffed 802.11 frame in monitor mode.
    # It’s not Wi-Fi payload from the client; it’s capture metadata like RSSI, rate, flags, and often channel frequency.
    if packet.haslayer(RadioTap):
        radiotap = packet[RadioTap]
        frequency = getattr(radiotap, "ChannelFrequency", None)
        if isinstance(frequency, int):
            channel = FREQ_TO_CHANNEL_24GHZ.get(frequency)
            if channel:
                return channel

    # Dot11Elt are 802.11 information elements inside management frames.
    # One of those elements is DS Parameter Set with ID = 3.
    # DS Parameter Set carries the AP/client channel as a single byte (for 2.4GHz usage).
    element = packet.getlayer(Dot11Elt)
    while element is not None:
        if getattr(element, "ID", None) == 3 and element.info:
            return int(element.info[0])
        element = element.payload.getlayer(Dot11Elt)

    return None


def extract_rssi_dbm_from_packet(packet):
    if not packet.haslayer(RadioTap):
        return None
    rt = packet[RadioTap]
    # Try common Radiotap RSSI attribute names
    raw = (
        getattr(rt, "dBm_AntSignal", None)
        if getattr(rt, "dBm_AntSignal", None) is not None
        else getattr(rt, "dBm_antsignal", None)
    )
    if raw is None:
        return None

    # Some drivers/scapy combos may expose unsigned byte (0..255).
    # Convert to signed dBm if needed.
    normalized = raw
    if isinstance(normalized, int) and normalized > 127:
        normalized -= 256

    try:
        rssi_dbm = int(normalized)
    except (TypeError, ValueError):
        logger.info(f"Discarded non-numeric RSSI value: raw={raw!r}")
        return None

    if -127 <= rssi_dbm <= 0:
        return rssi_dbm

    logger.debug(
        f"Discarded out-of-range RSSI value: raw={raw!r}, normalized={rssi_dbm!r}"
    )
    return None


def channel_hopper(interface: str, interval: float, channels=range(1, 14)):
    # FIXME: Consider only using, CHANNELS_24GHZ = [1, 6, 11], as they are non-overlapping channels and other will be included there.
    # This should allow for faster hopping on non-overlapping channels in monitor mode meaning more probe requests captured,
    # with less wasted time. Any probe request sent on channel 2, 3, 4, 5… will also be “seen” if you hop to 1 or 6, because
    # the signals overlap a bit—but it’s not guaranteed if the device is very low power or far away.
    try:
        while True:
            # There are 14 channels in the 2.4 GHz band. We use 13 as the 14th is
            # primarily restricted to Japan for use with 802.11b legacy devices.
            for channel in channels:
                _set_channel(interface, channel)
                logger.debug(f"Switched `{interface}` to channel {channel}.")
                time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Channel hopping stopped by the user.")
