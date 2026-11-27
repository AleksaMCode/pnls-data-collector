"""Unit tests for `parse_ip_packet`, the collector's handler for every captured frame."""

import unittest
from datetime import UTC, date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

from tests.support.collector_loader import import_collector_module
from tests.support.keys import test_rsa_key
from tests.support.probe_capture import beacon, probe_request
from util.util import decrypt_data

parser = import_collector_module("collector.wlan.parser")
wifi_helpers = parser.wifi_helpers

PARIS = ZoneInfo("Europe/Paris")
CAPTURED_AT = datetime(2026, 6, 14, 10, 15, 30, 123456, tzinfo=PARIS)
MAC = "00:1a:2b:00:00:01"


class ParserTestCase(unittest.TestCase):
    def setUp(self):
        self.firebase = self.patch_parser("publish_captured_date")
        self.local_backup = self.patch_parser("publish_captured_data_locally")
        self.patch_parser("RSA_KEY", new=test_rsa_key().publickey())
        self.patch_parser("CAPTURE_24_7", new=True)
        self.patch_parser("SSID_FILTER", new=[])
        self.patch_parser("MAC_FILTER", new=[])
        self.patch_parser("TIMEZONE", new="Europe/Paris")
        patcher = mock.patch.object(wifi_helpers, "WLAN_CHANNEL", 9)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_parser(self, name, **kwargs):
        patcher = mock.patch.object(parser, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def parse(self, packet) -> dict | None:
        """Runs the handler and returns the record sent to Firebase, if any."""
        parser.parse_ip_packet(packet)
        if not self.firebase.called:
            return None
        return self.firebase.call_args.args[0]

    def probe(self, **kwargs):
        kwargs.setdefault("ssid", b"CERN")
        kwargs.setdefault("at", CAPTURED_AT)
        return probe_request(kwargs.pop("mac", MAC), **kwargs)


class TestRecord(ParserTestCase):
    def test_record_fields(self):
        record = self.parse(self.probe(frequency=2437, rssi=-60))

        self.assertEqual(set(record), {"mac", "ssid", "channel", "timestamp"})
        self.assertEqual(record["ssid"], "CERN")
        self.assertEqual(record["channel"], 6)
        # Collector time zone, cut to milliseconds.
        self.assertEqual(record["timestamp"], "2026-06-14 10:15:30.123")

    def test_mac_is_encrypted_for_the_aggregator(self):
        record = self.parse(self.probe())

        self.assertNotIn(MAC, record["mac"])
        self.assertEqual(decrypt_data(test_rsa_key(), record["mac"]), MAC)

    def test_each_record_is_encrypted_differently(self):
        # RSA-OAEP is randomized, so the same MAC never gives the same ciphertext twice.
        first = self.parse(self.probe())["mac"]
        second = self.parse(self.probe())["mac"]

        self.assertNotEqual(first, second)

    def test_timestamp_uses_the_collector_time_zone(self):
        at_utc = datetime(
            2026, 6, 14, 8, 15, 30, tzinfo=UTC
        )  # 10:15:30 in Paris (CEST).

        record = self.parse(self.probe(at=at_utc))

        self.assertEqual(record["timestamp"], "2026-06-14 10:15:30.000")

    def test_record_is_sent_to_firebase_and_saved_locally(self):
        record = self.parse(self.probe())

        today = date.today().isoformat()
        self.firebase.assert_called_once_with(record, today)
        self.local_backup.assert_called_once_with(record, today)


class TestChannel(ParserTestCase):
    def test_radiotap_frequency_comes_first(self):
        self.assertEqual(
            self.parse(self.probe(frequency=2412, ds_channel=11))["channel"], 1
        )

    def test_ds_parameter_set_when_radiotap_has_no_channel(self):
        self.assertEqual(self.parse(self.probe(ds_channel=11))["channel"], 11)

    def test_current_hopping_channel_when_the_frame_has_none(self):
        self.assertEqual(self.parse(self.probe())["channel"], 9)


class TestSsid(ParserTestCase):
    def test_wildcard_probe_request_is_stored_as_star(self):
        self.assertEqual(self.parse(self.probe(ssid=b""))["ssid"], "*")

    def test_undecodable_ssid_is_also_stored_as_star(self):
        # The two cases cannot be told apart later (see the collector ticket).
        self.assertEqual(self.parse(self.probe(ssid=b"\xff\xfe"))["ssid"], "*")

    def test_utf8_ssid_is_kept(self):
        self.assertEqual(
            self.parse(self.probe(ssid="Café ☕".encode()))["ssid"], "Café ☕"
        )


class TestFilters(ParserTestCase):
    def test_filtered_ssid_is_not_recorded(self):
        self.patch_parser("SSID_FILTER", new=["CERN"])

        self.assertIsNone(self.parse(self.probe()))
        self.local_backup.assert_not_called()

    def test_filtered_mac_is_not_recorded(self):
        self.patch_parser("MAC_FILTER", new=[MAC])

        self.assertIsNone(self.parse(self.probe()))

    @unittest.expectedFailure
    def test_mac_filter_ignores_letter_case(self):
        """Known issue: scapy reports MACs in lowercase, so an uppercase MAC_FILTER entry never
        matches. Remove the decorator once the filter compares case-insensitively."""
        self.patch_parser("MAC_FILTER", new=[MAC.upper()])

        self.assertIsNone(self.parse(self.probe()))

    def test_other_frames_are_ignored(self):
        self.assertIsNone(self.parse(beacon("aa:bb:cc:dd:ee:ff", b"CERN")))

    def test_working_hours_limit_when_not_capturing_all_day(self):
        self.patch_parser("CAPTURE_24_7", new=False)
        cases = {True: True, False: False}  # Inside working hours -> recorded.
        for working_hours, recorded in cases.items():
            with self.subTest(working_hours=working_hours):
                self.firebase.reset_mock()
                with mock.patch.object(
                    parser, "is_working_hours", return_value=working_hours
                ) as is_working_hours:
                    record = self.parse(self.probe())

                self.assertEqual(record is not None, recorded)
                is_working_hours.assert_called_once_with("Europe/Paris")


class TestFailures(ParserTestCase):
    def test_local_backup_is_written_when_firebase_fails(self):
        self.firebase.side_effect = ConnectionError("Firebase down")

        parser.parse_ip_packet(self.probe())

        self.local_backup.assert_called_once()

    def test_local_backup_failure_is_logged_not_raised(self):
        self.local_backup.side_effect = OSError("disk full")

        parser.parse_ip_packet(self.probe())

        self.firebase.assert_called_once()


class TestNodeDate(ParserTestCase):
    @unittest.expectedFailure
    def test_node_date_uses_the_collector_time_zone(self):
        """Known issue (low while the devices run on Europe/Paris): the node date comes from the
        host's own time zone. On a host on UTC, a probe request at 00:30 in Paris is stamped
        with the new day but pushed into the previous day's node.
        Remove the decorator once the node date uses TIMEZONE."""
        host_now = datetime(
            2026, 6, 14, 22, 30, tzinfo=UTC
        )  # 00:30 on June 15 in Paris.

        class HostOnUtc(datetime):
            @classmethod
            def now(cls, tz=None):
                return host_now.astimezone(tz) if tz else host_now.replace(tzinfo=None)

        self.patch_parser("datetime", new=HostOnUtc)

        record = self.parse(self.probe(at=host_now))

        self.assertTrue(record["timestamp"].startswith("2026-06-15"))
        self.assertEqual(self.firebase.call_args.args[1], "2026-06-15")


if __name__ == "__main__":
    unittest.main()
