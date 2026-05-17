import logging
import sys
import types
import unittest

from scapy.layers.dot11 import Dot11Elt, RadioTap

# Avoid side effects from util.logger module initialization in unit tests.
fake_logger_module = types.ModuleType("util.logger")
fake_logger_module.get_logger = logging.getLogger
sys.modules["util.logger"] = fake_logger_module

from collector.wlan.helpers import (
    extract_channel_from_packet,
    extract_rssi_dbm_from_packet,
)


class FakePayload:
    def __init__(self, next_element=None):
        self._next_element = next_element

    def getlayer(self, layer):
        if layer is Dot11Elt:
            return self._next_element
        return None


class FakeDot11Element:
    def __init__(self, element_id, info, next_element=None):
        self.ID = element_id
        self.info = info
        self.payload = FakePayload(next_element)


class FakeRadioTap:
    def __init__(self, frequency=None, dbm_ant_signal=None, dbm_antsignal=None):
        self.ChannelFrequency = frequency
        self.dBm_AntSignal = dbm_ant_signal
        self.dBm_antsignal = dbm_antsignal


class FakePacket:
    def __init__(
        self,
        has_radiotap=False,
        frequency=None,
        dbm_ant_signal=None,
        dbm_antsignal=None,
        first_element=None,
    ):
        self._has_radiotap = has_radiotap
        self._radiotap = (
            FakeRadioTap(frequency, dbm_ant_signal, dbm_antsignal)
            if has_radiotap
            else None
        )
        self._first_element = first_element

    def haslayer(self, layer):
        return self._has_radiotap and layer is RadioTap

    def __getitem__(self, layer):
        if layer is RadioTap and self._radiotap is not None:
            return self._radiotap
        raise KeyError(layer)

    def getlayer(self, layer):
        if layer is Dot11Elt:
            return self._first_element
        return None


class TestExtractChannelFromPacket(unittest.TestCase):

    def test_extracts_channel_from_radiotap_frequency(self):
        packet = FakePacket(has_radiotap=True, frequency=2437)

        self.assertEqual(extract_channel_from_packet(packet), 6)

    def test_falls_back_to_ds_parameter_set(self):
        packet = FakePacket(
            first_element=FakeDot11Element(element_id=3, info=bytes([11]))
        )

        self.assertEqual(extract_channel_from_packet(packet), 11)

    def test_uses_ds_parameter_set_when_radiotap_frequency_is_unmapped(self):
        packet = FakePacket(
            has_radiotap=True,
            frequency=5500,
            first_element=FakeDot11Element(element_id=3, info=bytes([1])),
        )

        self.assertEqual(extract_channel_from_packet(packet), 1)

    def test_returns_none_when_no_channel_metadata_exists(self):
        packet = FakePacket()

        self.assertIsNone(extract_channel_from_packet(packet))


class TestExtractRssiDbmFromPacket(unittest.TestCase):

    def test_extracts_rssi_from_dbm_ant_signal(self):
        packet = FakePacket(has_radiotap=True, dbm_ant_signal=-63)

        self.assertEqual(extract_rssi_dbm_from_packet(packet), -63)

    def test_falls_back_to_dbm_antsignal(self):
        packet = FakePacket(has_radiotap=True, dbm_antsignal=-71)

        self.assertEqual(extract_rssi_dbm_from_packet(packet), -71)

    def test_converts_unsigned_rssi_to_signed_dbm(self):
        packet = FakePacket(has_radiotap=True, dbm_ant_signal=201)

        self.assertEqual(extract_rssi_dbm_from_packet(packet), -55)

    def test_discards_out_of_range_positive_rssi(self):
        packet = FakePacket(has_radiotap=True, dbm_ant_signal=101)

        self.assertIsNone(extract_rssi_dbm_from_packet(packet))

    def test_discards_out_of_range_negative_rssi(self):
        packet = FakePacket(has_radiotap=True, dbm_ant_signal=-150)

        self.assertIsNone(extract_rssi_dbm_from_packet(packet))

    def test_returns_none_without_radiotap(self):
        packet = FakePacket()

        self.assertIsNone(extract_rssi_dbm_from_packet(packet))

    def test_returns_none_when_rssi_fields_are_missing(self):
        packet = FakePacket(has_radiotap=True)

        self.assertIsNone(extract_rssi_dbm_from_packet(packet))


if __name__ == "__main__":
    unittest.main()
