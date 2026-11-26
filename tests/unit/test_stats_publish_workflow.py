"""Unit tests for the stats POST /stats workflow, with every reader and publisher replaced."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from tests.support.stats_loader import import_stats_module

main = import_stats_module("stats.main")
orm_helpers = import_stats_module("stats.core.orm.helpers")
supabase_helpers = import_stats_module("stats.core.supabase.helpers")

LATEST_IMPORT = date(2026, 6, 14)
DAILY_TOTALS = [
    SimpleNamespace(date=date(2026, 6, 14), ssid_count=3, mac_count=4, probes_count=9)
]
PUBLISHERS = (
    "publish_ssid_all",
    "public_mac_all",
    "public_probes_all",
    "publish_device_daily_imports_today",
    "publish_device_manufacturer_stats_all",
    "publish_manufacturer_stats_all",
    "publish_ssid_stats_all_batched",
    "publish_ssid_geo",
    "publish_unique_total_stats",
)


class PublishWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        # One parent mock, so the order of the calls across functions can be checked.
        self.workflow = mock.Mock()
        self.workflow.get_latest_import_date.return_value = LATEST_IMPORT
        self.workflow.get_daily_totals_all_devices.return_value = DAILY_TOTALS
        for name in (
            "get_latest_import_date",
            "get_daily_totals_all_devices",
            *PUBLISHERS,
        ):
            patcher = mock.patch.object(main, name, getattr(self.workflow, name))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def publish(self):
        return self.client.post("/stats")

    def steps(self) -> list[str]:
        return [call[0] for call in self.workflow.mock_calls if call[0]]

    def call(self, name):
        return getattr(self.workflow, name).call_args


class TestPublishWorkflow(PublishWorkflowTestCase):
    def test_every_table_is_published_in_order(self):
        response = self.publish()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            self.steps(),
            ["get_latest_import_date", "get_daily_totals_all_devices", *PUBLISHERS],
        )

    def test_daily_totals_are_read_from_the_latest_import(self):
        self.publish()

        self.assertEqual(
            self.call("get_daily_totals_all_devices").kwargs,
            {"start_date": LATEST_IMPORT},
        )

    def test_daily_metrics_publish_the_totals_that_were_read(self):
        self.publish()

        for name in ("publish_ssid_all", "public_mac_all", "public_probes_all"):
            with self.subTest(publisher=name):
                self.assertEqual(self.call(name).kwargs, {"daily_totals": DAILY_TOTALS})

    def test_dated_publishers_get_the_latest_import_date(self):
        self.publish()

        self.assertEqual(
            self.call("publish_device_daily_imports_today").kwargs,
            {"tz": "Europe/Paris", "import_date": LATEST_IMPORT},
        )
        self.assertEqual(
            self.call("publish_device_manufacturer_stats_all").kwargs,
            {"target_date": LATEST_IMPORT},
        )
        self.assertEqual(
            self.call("publish_ssid_stats_all_batched").kwargs,
            {"updated_from": LATEST_IMPORT},
        )
        self.assertEqual(
            self.call("publish_unique_total_stats").kwargs,
            {"target_date": LATEST_IMPORT},
        )

    def test_completed_response(self):
        response = self.publish()

        self.assertEqual(
            response.json(),
            {
                "status": "completed",
                "message": "Published daily totals to Supabase for 1 day(s), "
                "starting from 2026-06-14.",
                "start_date": "2026-06-14",
            },
        )

    def test_without_new_totals_only_the_ssid_geolocations_are_published(self):
        self.workflow.get_daily_totals_all_devices.return_value = []

        response = self.publish()

        self.assertEqual(
            response.json(),
            {
                "status": "skipped",
                "message": "No daily totals available from 2026-06-14.",
            },
        )
        self.assertEqual(
            self.steps(),
            [
                "get_latest_import_date",
                "get_daily_totals_all_devices",
                "publish_ssid_geo",
            ],
        )

    def test_failing_publisher_stops_the_run(self):
        self.workflow.publish_manufacturer_stats_all.side_effect = RuntimeError(
            "Supabase is down"
        )

        response = self.publish()

        self.assertEqual(response.status_code, 500)
        self.workflow.publish_ssid_stats_all_batched.assert_not_called()
        self.workflow.publish_unique_total_stats.assert_not_called()


class TestTestSafety(unittest.TestCase):
    def test_sessions_refuse_to_connect_unless_a_test_replaces_them(self):
        for helpers in (orm_helpers, supabase_helpers):
            with self.subTest(helpers=helpers.__name__):
                with self.assertRaisesRegex(RuntimeError, "without replacing it"):
                    helpers._session()


if __name__ == "__main__":
    unittest.main()
