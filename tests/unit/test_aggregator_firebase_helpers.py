"""Unit tests for the aggregator Firebase helpers, with `firebase_admin.db` replaced by a mock."""

import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from tests.support.aggregator_loader import (
    import_firebase_helpers,
    no_retry_wait,
    test_rsa_key,
)
from util.core.orm.models import Device
from util.util import encrypt_data

helpers = import_firebase_helpers()
STATS_NODE = helpers.FIREBASE_STATISTICS_NODE


def encrypted(mac: str) -> str:
    return encrypt_data(test_rsa_key().publickey(), mac)


def node(*records: dict) -> dict:
    return {"data": {f"record-{index}": record for index, record in enumerate(records)}}


class FirebaseDbMixin:
    """Replaces `db` in the helpers module and keeps one mock reference per path."""

    def setUp(self):
        super().setUp()
        self.references: dict[str, mock.MagicMock] = {}
        patcher = mock.patch.object(helpers, "db")
        self.db = patcher.start()
        self.addCleanup(patcher.stop)
        self.db.reference.side_effect = self._reference

        key_patcher = mock.patch.object(helpers, "RSA_KEY", test_rsa_key())
        key_patcher.start()
        self.addCleanup(key_patcher.stop)

    def _reference(self, path):
        return self.references.setdefault(path, mock.MagicMock(name=f"ref({path})"))

    def updates(self) -> dict[str, dict]:
        """Returns the payload of the last `update()` call for every path written to."""
        return {
            path: reference.update.call_args.args[0]
            for path, reference in self.references.items()
            if reference.update.called
        }


class TestFetchFirebaseNode(FirebaseDbMixin, unittest.TestCase):
    def test_reads_child_of_root(self):
        self._reference("/").child.return_value.get.return_value = {"data": {}}

        self.assertEqual(helpers.fetch_firebase_node("RPI-1-2026-06-14"), {"data": {}})
        self.references["/"].child.assert_called_once_with("RPI-1-2026-06-14")

    def test_retries_after_firebase_error(self):
        get = self._reference("/").child.return_value.get
        get.side_effect = [ConnectionError("timeout"), {"data": {}}]

        with no_retry_wait(helpers.fetch_firebase_node):
            self.assertEqual(helpers.fetch_firebase_node("node"), {"data": {}})
        self.assertEqual(get.call_count, 2)


class TestFetchData(FirebaseDbMixin, unittest.TestCase):
    TARGET_DATE = date(2026, 6, 14)

    def patch_nodes(self, nodes: dict):
        patcher = mock.patch.object(
            helpers, "fetch_firebase_node", side_effect=lambda key: nodes.get(key)
        )
        fetch = patcher.start()
        self.addCleanup(patcher.stop)
        return fetch

    def test_reads_one_node_per_device_for_the_date(self):
        fetch = self.patch_nodes({})

        helpers.fetch_data(self.TARGET_DATE)

        self.assertEqual(
            [call.args[0] for call in fetch.call_args_list],
            [f"{device.value}-2026-06-14" for device in Device],
        )

    def test_returns_decrypted_records_with_device(self):
        self.patch_nodes(
            {
                "RPI-1-2026-06-14": node(
                    {
                        "mac": encrypted("00:11:22:33:44:55"),
                        "ssid": "CERN",
                        "channel": 6,
                        "timestamp": "2026-06-14 08:00:00.000000",
                    }
                ),
                "RPI-2-2026-06-14": node(
                    {
                        "mac": encrypted("66:77:88:99:AA:BB"),
                        "ssid": "eduroam",
                        "channel": 11,
                        "timestamp": "2026-06-14 09:00:00.000000",
                    }
                ),
            }
        )

        records = helpers.fetch_data(self.TARGET_DATE)

        self.assertEqual(
            records,
            [
                {
                    "device": "RPI-1",
                    "mac": "00:11:22:33:44:55",
                    "ssid": "CERN",
                    "channel": 6,
                    "timestamp": "2026-06-14 08:00:00.000000",
                },
                {
                    "device": "RPI-2",
                    "mac": "66:77:88:99:AA:BB",
                    "ssid": "eduroam",
                    "channel": 11,
                    "timestamp": "2026-06-14 09:00:00.000000",
                },
            ],
        )

    def test_missing_nodes_and_nodes_without_data_are_skipped(self):
        self.patch_nodes({"RPI-1-2026-06-14": {}, "RPI-2-2026-06-14": {"other": 1}})

        self.assertEqual(helpers.fetch_data(self.TARGET_DATE), [])

    def test_firebase_error_stops_the_import(self):
        patcher = mock.patch.object(
            helpers, "fetch_firebase_node", side_effect=ConnectionError("down")
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        with self.assertRaisesRegex(Exception, "RPI-1.*RPI-1-2026-06-14") as raised:
            helpers.fetch_data(self.TARGET_DATE)
        self.assertIsInstance(raised.exception.__cause__, ConnectionError)

    @unittest.expectedFailure
    def test_record_without_mac_is_skipped(self):
        """Known bug: decrypt_data(None) raises, so one record without a MAC stops the import.

        Remove the decorator once fetch_data skips such records.
        """
        self.patch_nodes(
            {
                "RPI-1-2026-06-14": node(
                    {"ssid": "CERN", "channel": 6, "timestamp": "2026-06-14 08:00:00.0"}
                )
            }
        )

        self.assertEqual(helpers.fetch_data(self.TARGET_DATE), [])


class TestFetchAllData(FirebaseDbMixin, unittest.TestCase):
    def test_returns_records_from_start_date_up_to_today(self):
        today = date.today()
        in_window = today - timedelta(days=1)
        too_old = today - timedelta(days=5)
        future = today + timedelta(days=1)

        def record(day: date, mac: str) -> dict:
            return {"mac": mac, "ssid": "CERN", "timestamp": f"{day} 10:00:00.000000"}

        self._reference("/").get.return_value = {
            f"RPI-1-{in_window}": node(record(in_window, "a"), record(too_old, "b")),
            f"RPI-2-{today}": node(record(today, "c"), record(future, "d")),
        }

        records = helpers.fetch_all_data(today - timedelta(days=2))

        self.assertEqual(
            [(record["device"], record["mac"]) for record in records],
            [("RPI-1", "a"), ("RPI-2", "c")],
        )

    def test_empty_database_returns_no_records(self):
        self._reference("/").get.return_value = None

        self.assertEqual(helpers.fetch_all_data(date(2026, 1, 1)), [])


class TestPublishDailyStats(FirebaseDbMixin, unittest.TestCase):
    def capture(self, device="RPI-1", day=date(2026, 6, 14)):
        return SimpleNamespace(date=day, device=device, ssid=3, mac=7, probe_request=42)

    def test_capture_is_written_under_date_and_device(self):
        helpers.publish_daily_stats_capture_data(self.capture())

        self.assertEqual(
            self.updates(),
            {
                f"/{STATS_NODE}/daily/2026-06-14/RPI-1": {
                    "ssid": 3,
                    "mac": 7,
                    "probe_requests": 42,
                }
            },
        )

    def test_every_capture_is_published(self):
        helpers.publish_daily_stats_data([self.capture("RPI-1"), self.capture("RPI-2")])

        self.assertEqual(
            set(self.updates()),
            {
                f"/{STATS_NODE}/daily/2026-06-14/RPI-1",
                f"/{STATS_NODE}/daily/2026-06-14/RPI-2",
            },
        )


class TestDeprecatedPublishers(FirebaseDbMixin, unittest.TestCase):
    """The publishers replaced by Supabase. Still in the code, so still covered."""

    def patch_helper(self, name, **kwargs):
        patcher = mock.patch.object(helpers, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def test_publish_stats_data_writes_totals_and_daily_stats(self):
        self.patch_helper("get_total_captured_info_count", return_value=100)
        self.patch_helper("get_total_captured_mac_count", return_value=20)
        self.patch_helper("get_total_captured_ssid_count", return_value=5)
        self.patch_helper(
            "get_today_data_from_daily_captured_stats_per_device",
            return_value=[
                SimpleNamespace(
                    date=date(2026, 6, 14),
                    device="RPI-1",
                    ssid=1,
                    mac=2,
                    probe_request=3,
                )
            ],
        )

        with self.assertWarns(DeprecationWarning):
            stats = helpers.publish_stats_data()

        self.assertEqual(stats, {"total_count": 100, "mac_count": 20, "ssid_count": 5})
        updates = self.updates()
        self.assertEqual(updates[f"/{STATS_NODE}/total_count"]["count"], 100)
        self.assertEqual(updates[f"/{STATS_NODE}/mac_count"]["count"], 20)
        self.assertEqual(updates[f"/{STATS_NODE}/ssid_count"]["count"], 5)
        self.assertIn("timestamp", updates[f"/{STATS_NODE}/total_count"])
        self.assertIn(f"/{STATS_NODE}/daily/2026-06-14/RPI-1", updates)

    def test_publish_stats_data_returns_none_when_firebase_fails(self):
        for name in (
            "get_total_captured_info_count",
            "get_total_captured_mac_count",
            "get_total_captured_ssid_count",
        ):
            self.patch_helper(name, return_value=1)
        self.patch_helper(
            "get_today_data_from_daily_captured_stats_per_device", return_value=[]
        )
        self.db.reference.side_effect = ConnectionError("down")

        with self.assertWarns(DeprecationWarning):
            self.assertIsNone(helpers.publish_stats_data())

    def test_manufacturer_keys_drop_characters_firebase_forbids(self):
        self.patch_helper(
            "get_all_data_from_company_capture_summary",
            return_value=[
                SimpleNamespace(
                    company="Acme.Inc$#[x]/y",
                    country_alpha3="CHE",
                    total_occurrences=9,
                    percentage=1.5,
                )
            ],
        )

        with self.assertWarns(DeprecationWarning):
            helpers.publish_manufacturers_data()

        self.assertEqual(
            self.updates(),
            {
                # Each of . $ # [ ] / becomes one space.
                f"/{STATS_NODE}/manufacturers/Acme Inc   x  y": {
                    "country": "CHE",
                    "count": 9,
                    "percentage": 1.5,
                }
            },
        )

    def test_publish_devices_data_combines_location_and_totals(self):
        self.patch_helper(
            "get_all_data_from_location_mapping_resolved",
            return_value=[
                SimpleNamespace(device="RPI-1", location="61/R-202", coordinates="46,6")
            ],
        )
        totals = self.patch_helper(
            "get_device_total_captured_data",
            return_value=SimpleNamespace(ssid=4, probe_request=50, mac=8),
        )

        with self.assertWarns(DeprecationWarning):
            helpers.publish_devices_data()

        totals.assert_called_once_with(Device.RPI_1)
        self.assertEqual(
            self.updates(),
            {
                f"/{STATS_NODE}/devices/RPI-1": {
                    "location": "61/R-202",
                    "coordinates": "46,6",
                    "ssid": 4,
                    "probes": 50,
                    "mac": 8,
                }
            },
        )

    def test_publish_sankey_data_writes_one_entry_per_device_and_company(self):
        self.patch_helper(
            "get_all_data_from_company_capture_summary_by_device",
            side_effect=lambda device: [
                SimpleNamespace(company=f"Org/{device.value}", country_alpha3="FRA")
            ],
        )

        with self.assertWarns(DeprecationWarning):
            helpers.publish_sankey_data()

        self.assertEqual(
            self.updates(),
            {
                f"/{STATS_NODE}/sankey/{device.value}/Org {device.value}": {
                    "country": "FRA"
                }
                for device in Device
            },
        )

    def test_publisher_errors_are_logged_not_raised(self):
        self.patch_helper(
            "get_all_data_from_company_capture_summary",
            return_value=[
                SimpleNamespace(
                    company="A", country_alpha3="X", total_occurrences=1, percentage=1
                )
            ],
        )
        self.patch_helper(
            "get_all_data_from_location_mapping_resolved",
            return_value=[SimpleNamespace(device="RPI-1", location="", coordinates="")],
        )
        self.patch_helper("get_device_total_captured_data", side_effect=RuntimeError)
        self.patch_helper(
            "get_all_data_from_company_capture_summary_by_device",
            side_effect=RuntimeError,
        )
        self.db.reference.side_effect = ConnectionError("down")

        for publisher in (
            helpers.publish_manufacturers_data,
            helpers.publish_devices_data,
            helpers.publish_sankey_data,
        ):
            with self.subTest(publisher=publisher.__name__):
                with self.assertWarns(DeprecationWarning):
                    self.assertIsNone(publisher())


class TestDelete(FirebaseDbMixin, unittest.TestCase):
    def test_each_delete_removes_its_own_path(self):
        cases = {
            helpers.delete_all: "/",
            helpers.delete_stats: "/stats",
            helpers.delete_manufacturers: f"/{STATS_NODE}/manufacturers",
            helpers.delete_sankey: f"/{STATS_NODE}/sankey",
        }
        for delete, path in cases.items():
            with self.subTest(path=path):
                self.references.clear()

                delete()

                self.assertEqual(
                    [p for p, ref in self.references.items() if ref.delete.called],
                    [path],
                )


class TestDownloadToday(FirebaseDbMixin, unittest.TestCase):
    def test_groups_today_data_by_device(self):
        today = date.today()
        entries = {"record-0": {"ssid": "CERN"}}
        nodes = {f"RPI-1-{today}": {"data": entries}}

        with mock.patch.object(
            helpers, "fetch_firebase_node", side_effect=lambda key: nodes.get(key)
        ):
            result = helpers.download_today()

        self.assertEqual(dict(result), {Device.RPI_1: [entries]})

    @unittest.expectedFailure
    def test_firebase_error_skips_the_device(self):
        """Known bug: after an error, `node_value` is undefined for the first device and stale
        for later ones, so download_today crashes or repeats the previous device's data.

        Remove the decorator once a failed device is skipped.
        """
        with mock.patch.object(
            helpers, "fetch_firebase_node", side_effect=ConnectionError("down")
        ):
            self.assertEqual(dict(helpers.download_today()), {})


if __name__ == "__main__":
    unittest.main()
