"""Unit tests for the collector's Wi-Fi helpers: frame metadata, interface and channel control."""

import subprocess
import unittest
from unittest import mock

from scapy.layers.dot11 import Dot11Elt, RadioTap

from collector.wlan import helpers
from collector.wlan.helpers import (
    extract_channel_from_packet,
    extract_rssi_dbm_from_packet,
)
from tests.support.probe_capture import probe_request

CHANNELS_1_TO_13 = range(1, 14)


class StopLoop(BaseException):
    """Ends the collector's endless loops in tests. Not an Exception, so they cannot catch it."""


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


class ChannelsMixin:
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(helpers, "CHANNELS", CHANNELS_1_TO_13)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestExtractChannelFromPacket(ChannelsMixin, unittest.TestCase):

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

    def test_non_numeric_frequency_is_ignored(self):
        packet = FakePacket(
            has_radiotap=True,
            frequency="2437",
            first_element=FakeDot11Element(element_id=3, info=bytes([4])),
        )

        self.assertEqual(extract_channel_from_packet(packet), 4)

    def test_empty_ds_element_is_skipped(self):
        packet = FakePacket(first_element=FakeDot11Element(element_id=3, info=b""))

        self.assertIsNone(extract_channel_from_packet(packet))


class TestExtractChannelFromRealFrames(ChannelsMixin, unittest.TestCase):
    """Frames built and parsed back by scapy, so the RadioTap field names are the real ones."""

    def test_every_2_4_ghz_frequency(self):
        for frequency, channel in helpers.FREQ_TO_CHANNEL_24GHZ.items():
            if channel not in CHANNELS_1_TO_13:
                continue
            with self.subTest(frequency=frequency):
                packet = probe_request("00:11:22:33:44:55", frequency=frequency)

                self.assertEqual(extract_channel_from_packet(packet), channel)

    def test_ds_element_is_found_after_other_elements(self):
        # probe_request puts the SSID and supported rates before the DS Parameter Set.
        packet = probe_request("00:11:22:33:44:55", b"CERN", ds_channel=11)

        self.assertEqual(extract_channel_from_packet(packet), 11)

    def test_channel_14_is_not_captured(self):
        # 2484 MHz is channel 14, outside CHANNELS, so the DS element decides.
        self.assertEqual(
            extract_channel_from_packet(
                probe_request("00:11:22:33:44:55", frequency=2484, ds_channel=1)
            ),
            1,
        )
        self.assertIsNone(
            extract_channel_from_packet(
                probe_request("00:11:22:33:44:55", ds_channel=14)
            )
        )

    def test_5_ghz_frequency_is_not_a_channel(self):
        self.assertIsNone(
            extract_channel_from_packet(
                probe_request("00:11:22:33:44:55", frequency=5500)
            )
        )

    def test_frame_without_channel_metadata(self):
        self.assertIsNone(
            extract_channel_from_packet(probe_request("00:11:22:33:44:55"))
        )


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

    def test_range_limits(self):
        cases = {-127: -127, 0: 0, 1: None, -128: None}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                packet = FakePacket(has_radiotap=True, dbm_ant_signal=raw)

                self.assertEqual(extract_rssi_dbm_from_packet(packet), expected)

    def test_non_numeric_rssi_is_discarded(self):
        packet = FakePacket(has_radiotap=True, dbm_ant_signal="strong")

        self.assertIsNone(extract_rssi_dbm_from_packet(packet))

    def test_rssi_from_a_real_frame(self):
        for rssi in (-30, -60, -95):
            with self.subTest(rssi=rssi):
                packet = probe_request("00:11:22:33:44:55", rssi=rssi)

                self.assertEqual(extract_rssi_dbm_from_packet(packet), rssi)

    def test_real_frame_without_signal_field(self):
        packet = probe_request("00:11:22:33:44:55", frequency=2412)

        self.assertIsNone(extract_rssi_dbm_from_packet(packet))


def iwconfig_output(interface: str, mode: str | None) -> subprocess.CompletedProcess:
    if mode is None:
        stdout = ""  # iwconfig prints the error to stderr for an unknown interface.
    else:
        stdout = (
            f"{interface}  IEEE 802.11  Mode:{mode}  Frequency:2.412 GHz  "
            "Tx-Power=20 dBm\n          Retry short limit:7   RTS thr:off\n"
        )
    return subprocess.CompletedProcess(["iwconfig", interface], 0, stdout, "")


class TestCheckInterfaceMode(unittest.TestCase):
    def setUp(self):
        for name, value in (("INTERFACE", ""), ("INTERFACES", ["wlan1", "wlan0"])):
            patcher = mock.patch.object(helpers, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_with(self, modes: dict):
        def fake_run(command, **kwargs):
            interface = command[1]
            return iwconfig_output(interface, modes.get(interface))

        with mock.patch.object(helpers.subprocess, "run", side_effect=fake_run) as run:
            result = helpers.check_interface_mode()
        return result, run

    def test_first_interface_in_monitor_mode_is_used(self):
        result, run = self.run_with({"wlan1mon": "Monitor", "wlan0mon": "Monitor"})

        self.assertTrue(result)
        self.assertEqual(helpers.INTERFACE, "wlan1mon")
        run.assert_called_once_with(
            ["iwconfig", "wlan1mon"], capture_output=True, text=True
        )

    def test_falls_back_to_the_next_interface(self):
        result, _ = self.run_with({"wlan0mon": "Monitor"})

        self.assertTrue(result)
        self.assertEqual(helpers.INTERFACE, "wlan0mon")

    def test_interface_in_managed_mode_is_not_used(self):
        result, _ = self.run_with({"wlan1mon": "Managed", "wlan0mon": "Managed"})

        self.assertFalse(result)
        self.assertEqual(helpers.INTERFACE, "")

    def test_missing_iwconfig(self):
        with mock.patch.object(
            helpers.subprocess, "run", side_effect=FileNotFoundError("iwconfig")
        ):
            self.assertFalse(helpers.check_interface_mode())


class TestSetChannel(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(helpers, "WLAN_CHANNEL", 1)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_switches_the_channel(self):
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(helpers.subprocess, "run", return_value=done) as run:
            helpers._set_channel("wlan1mon", 6)

        run.assert_called_once_with(
            ["iw", "dev", "wlan1mon", "set", "channel", "6"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(helpers.WLAN_CHANNEL, 6)

    def test_failed_switch_keeps_the_current_channel(self):
        failed = subprocess.CompletedProcess([], 1, "", "Device or resource busy")
        with mock.patch.object(helpers.subprocess, "run", return_value=failed):
            helpers._set_channel("wlan1mon", 6)

        self.assertEqual(helpers.WLAN_CHANNEL, 1)

    @unittest.expectedFailure
    def test_missing_iw_is_logged_not_raised(self):
        """Known bug: only CalledProcessError is caught, which subprocess.run never raises
        without check=True. A missing `iw` ends the channel-hopper thread.
        Remove the decorator once every error is caught."""
        with mock.patch.object(
            helpers.subprocess, "run", side_effect=FileNotFoundError("iw")
        ):
            helpers._set_channel("wlan1mon", 6)


class TestChannelHopper(unittest.TestCase):
    def setUp(self):
        self.set_channel = self.patch_helpers("_set_channel")
        self.sleep = self.patch_helpers("time").sleep
        self.patch_helpers("CAPTURE_24_7", new=True)

    def patch_helpers(self, name, **kwargs):
        patcher = mock.patch.object(helpers, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def stop_after_sleeps(self, count: int):
        self.sleep.side_effect = [None] * (count - 1) + [StopLoop()]

    def test_cycles_through_the_channels(self):
        self.stop_after_sleeps(5)

        with self.assertRaises(StopLoop):
            helpers.channel_hopper("wlan1mon", 0.1, channels=[1, 6, 11])

        self.assertEqual(
            [call.args for call in self.set_channel.call_args_list],
            [
                ("wlan1mon", 1),
                ("wlan1mon", 6),
                ("wlan1mon", 11),
                ("wlan1mon", 1),
                ("wlan1mon", 6),
            ],
        )
        self.sleep.assert_called_with(0.1)

    def test_ctrl_c_stops_hopping_quietly(self):
        self.sleep.side_effect = KeyboardInterrupt

        helpers.channel_hopper("wlan1mon", 0.1, channels=[1])

        self.set_channel.assert_called_once()

    def test_hops_during_working_hours_when_not_capturing_all_day(self):
        self.patch_helpers("CAPTURE_24_7", new=False)
        self.patch_helpers("is_working_hours", return_value=True)
        self.stop_after_sleeps(1)

        with self.assertRaises(StopLoop):
            helpers.channel_hopper("wlan1mon", 0.1, channels=[3])

        self.set_channel.assert_called_once_with("wlan1mon", 3)

    @unittest.expectedFailure
    def test_waits_outside_working_hours(self):
        """Known bug: outside working hours the loop `continue`s without sleeping and runs at
        100% CPU. Remove the decorator once it waits before checking again."""
        self.patch_helpers("CAPTURE_24_7", new=False)
        self.patch_helpers("is_working_hours", side_effect=[False, StopLoop()])

        with self.assertRaises(StopLoop):
            helpers.channel_hopper("wlan1mon", 0.1, channels=[1])

        self.set_channel.assert_not_called()
        self.sleep.assert_called()


if __name__ == "__main__":
    unittest.main()
