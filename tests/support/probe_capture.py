"""Builds real 802.11 frames with scapy, as a monitor-mode Wi-Fi card delivers them.

Every frame is built, turned into bytes and parsed again, so the tests see the fields scapy
really produces from raw bytes, not the values they were built with. `write_capture()` saves
frames to a .pcap file, which `scapy.sendrecv.sniff(offline=...)` reads like a live capture.
"""

from datetime import datetime
from pathlib import Path

from scapy.compat import raw
from scapy.layers.dot11 import (
    Dot11,
    Dot11Beacon,
    Dot11Elt,
    Dot11ProbeReq,
    RadioTap,
)
from scapy.utils import wrpcap

BROADCAST = "ff:ff:ff:ff:ff:ff"
CHANNEL_FLAGS_2GHZ = 0x0080
SUPPORTED_RATES = b"\x02\x04\x0b\x16"

# 802.11 information element IDs.
ELEMENT_SSID = 0
ELEMENT_RATES = 1
ELEMENT_DS_PARAMETER_SET = 3


def _radiotap(frequency: int | None, rssi: int | None) -> RadioTap:
    present, fields = [], {}
    if frequency is not None:
        present.append("Channel")
        fields.update(ChannelFrequency=frequency, ChannelFlags=CHANNEL_FLAGS_2GHZ)
    if rssi is not None:
        present.append("dBm_AntSignal")
        fields["dBm_AntSignal"] = rssi
    return RadioTap(present="+".join(present), **fields) if present else RadioTap()


def _as_received(frame, at: datetime | None):
    """Returns the frame parsed from its own bytes, with the capture time set."""
    packet = RadioTap(raw(frame))
    if at is not None:
        packet.time = at.timestamp()
    return packet


def probe_request(
    mac: str,
    ssid: bytes = b"",
    *,
    frequency: int | None = None,
    ds_channel: int | None = None,
    rssi: int | None = None,
    at: datetime | None = None,
):
    """A probe request from `mac`. `ssid=b""` is a wildcard (broadcast) probe request.

    `frequency` goes into the RadioTap header, `ds_channel` into a DS Parameter Set element
    after the SSID and supported rates, as phones send them.
    """
    elements = Dot11Elt(ID=ELEMENT_SSID, info=ssid) / Dot11Elt(
        ID=ELEMENT_RATES, info=SUPPORTED_RATES
    )
    if ds_channel is not None:
        elements = elements / Dot11Elt(
            ID=ELEMENT_DS_PARAMETER_SET, info=bytes([ds_channel])
        )
    frame = (
        _radiotap(frequency, rssi)
        / Dot11(type=0, subtype=4, addr1=BROADCAST, addr2=mac, addr3=BROADCAST)
        / Dot11ProbeReq()
        / elements
    )
    return _as_received(frame, at)


def beacon(mac: str, ssid: bytes, *, at: datetime | None = None):
    """A beacon from an access point, which the collector must not record."""
    frame = (
        RadioTap()
        / Dot11(type=0, subtype=8, addr1=BROADCAST, addr2=mac, addr3=mac)
        / Dot11Beacon()
        / Dot11Elt(ID=ELEMENT_SSID, info=ssid)
    )
    return _as_received(frame, at)


def write_capture(path: Path, packets) -> Path:
    """Saves the frames as a .pcap file with the RadioTap link type."""
    wrpcap(str(path), list(packets))
    return path


def is_probe_request(packet) -> bool:
    """The `lfilter` the sniffer uses."""
    return packet.haslayer(Dot11ProbeReq)
