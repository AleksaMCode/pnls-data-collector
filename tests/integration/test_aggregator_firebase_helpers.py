"""Integration tests for the aggregator Firebase helpers against the Firebase Database emulator."""

import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from tests.integration.containers import (
    assert_firebase_is_emulator,
    connect_firebase_emulator,
    requires_firebase,
)
from tests.support.aggregator_loader import import_firebase_helpers, test_rsa_key
from util.core.orm.models import Device
from util.util import encrypt_data


def device_node(*records: dict) -> dict:
    return {"data": {f"r{index}": record for index, record in enumerate(records)}}


def probe(mac: str, ssid: str, timestamp: str, channel: int = 6) -> dict:
    return {
        "mac": encrypt_data(test_rsa_key().publickey(), mac),
        "ssid": ssid,
        "channel": channel,
        "timestamp": timestamp,
    }


@requires_firebase
class TestFirebaseHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = import_firebase_helpers()
        connect_firebase_emulator()
        cls.db = cls.helpers.db
        cls.stats = cls.helpers.FIREBASE_STATISTICS_NODE

    def setUp(self):
        assert_firebase_is_emulator()
        self.db.reference("/").delete()
        patcher = mock.patch.object(self.helpers, "RSA_KEY", test_rsa_key())
        patcher.start()
        self.addCleanup(patcher.stop)

    def seed(self, path: str, value):
        self.db.reference(path).set(value)

    def read(self, path: str):
        return self.db.reference(path).get()

    def patch_helper(self, name, **kwargs):
        patcher = mock.patch.object(self.helpers, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def test_fetch_firebase_node(self):
        node = device_node({"ssid": "CERN"})
        self.seed("/RPI-1-2026-06-14", node)

        self.assertEqual(self.helpers.fetch_firebase_node("RPI-1-2026-06-14"), node)
        self.assertIsNone(self.helpers.fetch_firebase_node("RPI-1-2026-06-15"))

    def test_fetch_data_decrypts_the_nodes_of_the_date(self):
        self.seed(
            "/RPI-1-2026-06-14",
            device_node(
                probe("00:11:22:33:44:55", "CERN", "2026-06-14 08:00:00.000000", 1),
                probe("00:11:22:33:44:66", "eduroam", "2026-06-14 08:05:00.000000"),
            ),
        )
        self.seed(
            "/RPI-3-2026-06-14",
            device_node(probe("66:77:88:99:AA:BB", "Home", "2026-06-14 09:00:00.0")),
        )
        # Another date of the same device is not read.
        self.seed(
            "/RPI-1-2026-06-13",
            device_node(probe("00:00:00:00:00:01", "Old", "2026-06-13 09:00:00.0")),
        )

        records = self.helpers.fetch_data(date(2026, 6, 14))

        self.assertEqual(
            [(r["device"], r["mac"], r["ssid"], r["channel"]) for r in records],
            [
                ("RPI-1", "00:11:22:33:44:55", "CERN", 1),
                ("RPI-1", "00:11:22:33:44:66", "eduroam", 6),
                ("RPI-3", "66:77:88:99:AA:BB", "Home", 6),
            ],
        )
        self.assertEqual(records[0]["timestamp"], "2026-06-14 08:00:00.000000")

    def test_fetch_data_without_nodes_returns_nothing(self):
        self.assertEqual(self.helpers.fetch_data(date(2026, 6, 14)), [])

    def test_fetch_all_data_filters_by_date(self):
        today = date.today()
        start = today - timedelta(days=2)
        self.seed(
            f"/RPI-1-{start}",
            device_node(
                {"mac": "a", "ssid": "x", "timestamp": f"{start} 10:00:00.000000"},
                {
                    "mac": "b",
                    "ssid": "x",
                    "timestamp": f"{start - timedelta(days=1)} 10:00:00.0",
                },
            ),
        )
        self.seed(
            f"/RPI-2-{today}",
            device_node(
                {"mac": "c", "ssid": "y", "timestamp": f"{today} 23:59:59.999999"}
            ),
        )

        records = self.helpers.fetch_all_data(start)

        self.assertCountEqual(
            [(r["device"], r["mac"]) for r in records], [("RPI-1", "a"), ("RPI-2", "c")]
        )

    def test_publish_daily_stats_data(self):
        captures = [
            SimpleNamespace(
                date=date(2026, 6, 14), device="RPI-1", ssid=3, mac=7, probe_request=42
            ),
            SimpleNamespace(
                date=date(2026, 6, 14), device="RPI-2", ssid=1, mac=2, probe_request=5
            ),
        ]

        with self.assertWarns(DeprecationWarning):
            self.helpers.publish_daily_stats_data(captures)

        self.assertEqual(
            self.read(f"/{self.stats}/daily/2026-06-14"),
            {
                "RPI-1": {"ssid": 3, "mac": 7, "probe_requests": 42},
                "RPI-2": {"ssid": 1, "mac": 2, "probe_requests": 5},
            },
        )

    def test_daily_stats_update_keeps_other_fields(self):
        self.seed(f"/{self.stats}/daily/2026-06-14/RPI-1", {"note": "kept"})

        with self.assertWarns(DeprecationWarning):
            self.helpers.publish_daily_stats_capture_data(
                SimpleNamespace(
                    date=date(2026, 6, 14),
                    device="RPI-1",
                    ssid=1,
                    mac=1,
                    probe_request=1,
                )
            )

        self.assertEqual(
            self.read(f"/{self.stats}/daily/2026-06-14/RPI-1")["note"], "kept"
        )

    def test_publish_stats_data(self):
        self.patch_helper("get_total_captured_info_count", return_value=100)
        self.patch_helper("get_total_captured_mac_count", return_value=20)
        self.patch_helper("get_total_captured_ssid_count", return_value=5)
        self.patch_helper(
            "get_today_data_from_daily_captured_stats_per_device", return_value=[]
        )

        with self.assertWarns(DeprecationWarning):
            self.helpers.publish_stats_data()

        stats = self.read(f"/{self.stats}")
        self.assertEqual(
            {
                key: stats[key]["count"]
                for key in ("total_count", "mac_count", "ssid_count")
            },
            {"total_count": 100, "mac_count": 20, "ssid_count": 5},
        )

    def test_manufacturer_names_become_valid_firebase_keys(self):
        # Firebase rejects keys containing . $ # [ ] /, so this write fails without the cleanup.
        self.patch_helper(
            "get_all_data_from_company_capture_summary",
            return_value=[
                SimpleNamespace(
                    company="Acme Corp. [EU]",
                    country_alpha3="CHE",
                    total_occurrences=9,
                    percentage=1.5,
                )
            ],
        )

        with self.assertWarns(DeprecationWarning):
            self.helpers.publish_manufacturers_data()

        self.assertEqual(
            self.read(f"/{self.stats}/manufacturers"),
            {"Acme Corp   EU ": {"country": "CHE", "count": 9, "percentage": 1.5}},
        )

    def test_publish_devices_and_sankey_data(self):
        self.patch_helper(
            "get_all_data_from_location_mapping_resolved",
            return_value=[
                SimpleNamespace(device="RPI-1", location="61/R-202", coordinates="46,6")
            ],
        )
        self.patch_helper(
            "get_device_total_captured_data",
            return_value=SimpleNamespace(ssid=4, probe_request=50, mac=8),
        )
        self.patch_helper(
            "get_all_data_from_company_capture_summary_by_device",
            side_effect=lambda device: [
                SimpleNamespace(company="Org/A", country_alpha3="FRA")
            ],
        )

        with self.assertWarns(DeprecationWarning):
            self.helpers.publish_devices_data()
        with self.assertWarns(DeprecationWarning):
            self.helpers.publish_sankey_data()

        self.assertEqual(
            self.read(f"/{self.stats}/devices/RPI-1"),
            {
                "location": "61/R-202",
                "coordinates": "46,6",
                "ssid": 4,
                "probes": 50,
                "mac": 8,
            },
        )
        self.assertEqual(
            self.read(f"/{self.stats}/sankey"),
            {device.value: {"Org A": {"country": "FRA"}} for device in Device},
        )

    def test_deletes_remove_only_their_own_part(self):
        tree = {
            self.stats: {
                "manufacturers": {"A": {"count": 1}},
                "sankey": {"RPI-1": {"A": {"country": "X"}}},
                "daily": {"2026-06-14": {"RPI-1": {"ssid": 1}}},
            },
            "RPI-1-2026-06-14": {"data": {"r0": {"ssid": "CERN"}}},
        }
        self.seed("/", tree)

        self.helpers.delete_manufacturers()
        self.assertEqual(set(self.read(f"/{self.stats}")), {"sankey", "daily"})

        self.helpers.delete_sankey()
        self.assertEqual(set(self.read(f"/{self.stats}")), {"daily"})

        self.helpers.delete_stats()
        self.assertEqual(set(self.read("/")), {"RPI-1-2026-06-14"})

        self.helpers.delete_all()
        self.assertIsNone(self.read("/"))

    def test_download_today(self):
        today = date.today()
        entries = {"r0": {"ssid": "CERN"}}
        self.seed(f"/RPI-2-{today}", {"data": entries})

        self.assertEqual(dict(self.helpers.download_today()), {Device.RPI_2: [entries]})


if __name__ == "__main__":
    unittest.main()
