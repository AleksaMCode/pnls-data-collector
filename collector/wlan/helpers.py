import subprocess
import time

from yaspin import yaspin

from collector.settings import INTERFACES
from util.logger import get_logger

INTERFACE = ""
logger = get_logger(__name__)
# Current WLAN Channel for 2.4 GHz range.
WLAN_CHANNEL = 1


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
    WLAN_CHANNEL = channel
    try:
        result = subprocess.run(
            ["iw", "dev", interface, "set", "channel", str(channel)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"Failed to set channel {channel}: {result.stderr}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to set channel {channel} on {interface}: {e.stderr}")


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
