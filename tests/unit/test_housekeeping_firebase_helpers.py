"""Unit tests for the housekeeping Firebase backup download and deletes, on an in-memory Firebase."""

import unittest
from datetime import UTC, datetime
from unittest import mock

from tenacity import RetryError

from tests.support.aggregator_loader import no_retry_wait
from tests.support.fake_firebase import FakeRealtimeDatabase
from tests.support.housekeeping_loader import import_housekeeping_module

helpers = import_housekeeping_module("firebase_housekeeping.core.firebase.helpers")

# 23:30 UTC on June 14 is already June 15 in Paris (CEST), the collectors' time zone.
NOW_UTC = datetime(2026, 6, 14, 23, 30, tzinfo=UTC)
TODAY = "2026-06-15"
YESTERDAY = "2026-06-14"
STATS = {"devices": {"RPI-1": {"count": 3}}, "total_count": 3}


def entries(count: int, prefix: str = "e") -> dict:
    return {
        f"{prefix}{index}": {"ssid": "CERN", "channel": 6} for index in range(count)
    }


def seed_tree() -> dict:
    return {
        "stats": STATS,
        f"RPI-1-{YESTERDAY}": {
            "data": entries(3),
            "status": {"status": "working", "timestamp": f"{YESTERDAY} 22:00:00.000"},
        },
        f"RPI-2-{YESTERDAY}": {"data": entries(2)},
        f"RPI-2-{TODAY}": {"data": entries(1)},
    }


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW_UTC.astimezone(tz)


class FirebaseHelpersTestCase(unittest.TestCase):
    def setUp(self):
        self.firebase = FakeRealtimeDatabase(seed_tree())
        for name, value in (
            ("db", self.firebase),
            ("datetime", FixedClock),
            ("TIMEZONE", "Europe/Paris"),
            ("FIREBASE_STATISTICS_NODE", "stats"),
            ("BULK_DELETE_SIZE", 2),
        ):
            patcher = mock.patch.object(helpers, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.enterContext(no_retry_wait(helpers.delete_all_by_entry_nodes))

    def use_tree(self, tree: dict):
        self.firebase.tree = tree


class TestDownloadAll(FirebaseHelpersTestCase):
    def test_nodes_are_grouped_by_device(self):
        data = helpers.download_all()

        self.assertEqual(
            dict(data),
            {
                "RPI-1": [seed_tree()[f"RPI-1-{YESTERDAY}"]],
                "RPI-2": [
                    seed_tree()[f"RPI-2-{YESTERDAY}"],
                    seed_tree()[f"RPI-2-{TODAY}"],
                ],
            },
        )

    def test_statistics_node_is_not_backed_up(self):
        data = helpers.download_all()

        self.assertNotIn("stats", data)
        self.assertNotIn(STATS, [node for nodes in data.values() for node in nodes])

    def test_empty_firebase_downloads_nothing(self):
        self.use_tree({})

        with self.assertLogs(helpers.logger, "INFO") as logs:
            self.assertEqual(dict(helpers.download_all()), {})

        self.assertIn("No data found in Firebase.", logs.output[0])

    def test_firebase_is_not_changed(self):
        helpers.download_all()

        self.assertEqual(self.firebase.tree, seed_tree())

    @unittest.expectedFailure
    def test_device_missing_from_the_enum_is_backed_up(self):
        """Known bug: only RPI-1 to RPI-3 are backed up, but every device node is deleted.
        Remove the decorator once both use the same set of nodes.
        """
        self.firebase.tree[f"RPI-4-{YESTERDAY}"] = {"data": entries(1)}

        self.assertIn("RPI-4", helpers.download_all())

    @unittest.expectedFailure
    def test_node_that_is_not_a_device_node_is_skipped(self):
        """Known bug: a key without a trailing date raises AttributeError and fails the whole
        backup. Remove the decorator once such keys are skipped.
        """
        self.firebase.tree["test-node"] = {"value": 1}

        self.assertEqual(sorted(helpers.download_all()), ["RPI-1", "RPI-2"])


class TestDeleteAllByEntryNodes(FirebaseHelpersTestCase):
    def test_only_statistics_and_todays_nodes_are_kept(self):
        helpers.delete_all_by_entry_nodes()

        self.assertEqual(
            self.firebase.tree,
            {"stats": STATS, f"RPI-2-{TODAY}": seed_tree()[f"RPI-2-{TODAY}"]},
        )

    def test_today_is_the_date_in_the_collector_time_zone(self):
        # Yesterday's node in Paris is "today" in UTC; it is deleted.
        helpers.delete_all_by_entry_nodes()

        self.assertNotIn(f"RPI-1-{YESTERDAY}", self.firebase.tree)
        self.assertIn(f"RPI-2-{TODAY}", self.firebase.tree)

    def test_each_child_of_a_node_is_deleted_in_its_own_request(self):
        helpers.delete_all_by_entry_nodes()

        deletes = [path for call, path in self.firebase.calls if call == "delete"]
        self.assertEqual(
            deletes,
            [
                f"/RPI-1-{YESTERDAY}/data",
                f"/RPI-1-{YESTERDAY}/status",
                f"/RPI-2-{YESTERDAY}/data",
            ],
        )

    def test_node_without_children_is_deleted_whole(self):
        self.use_tree({f"RPI-3-{YESTERDAY}": "leaf", "stats": STATS})

        helpers.delete_all_by_entry_nodes()

        self.assertEqual(self.firebase.tree, {"stats": STATS})

    def test_failed_bulk_delete_falls_back_to_batches_of_entries(self):
        self.use_tree({f"RPI-1-{YESTERDAY}": {"data": entries(5)}})
        self.firebase.fail_delete.add(f"/RPI-1-{YESTERDAY}/data")

        helpers.delete_all_by_entry_nodes()

        self.assertEqual(self.firebase.tree, {})
        updates = [path for call, path in self.firebase.calls if call == "update"]
        # Five entries in batches of BULK_DELETE_SIZE (2).
        self.assertEqual(updates, [f"/RPI-1-{YESTERDAY}/data"] * 3)

    def test_failed_bulk_delete_is_logged(self):
        self.use_tree({f"RPI-1-{YESTERDAY}": {"data": entries(1)}})
        self.firebase.fail_delete.add(f"/RPI-1-{YESTERDAY}/data")

        with self.assertLogs(helpers.logger, "WARNING") as logs:
            helpers.delete_all_by_entry_nodes()

        self.assertIn("Falling back to entry-level delete", logs.output[0])

    def test_failed_fallback_is_retried_then_raised(self):
        self.use_tree({f"RPI-1-{YESTERDAY}": {"data": entries(1)}})
        self.firebase.fail_delete.add(f"/RPI-1-{YESTERDAY}/data")
        self.firebase.fail_update.add(f"/RPI-1-{YESTERDAY}/data")

        with self.assertRaises(RetryError):
            helpers.delete_all_by_entry_nodes()

        # One fallback update per attempt, out of 10 attempts.
        updates = [path for call, path in self.firebase.calls if call == "update"]
        self.assertEqual(len(updates), 10)

    def test_transient_error_is_retried(self):
        self.firebase.fail_get["/"] = 1

        helpers.delete_all_by_entry_nodes()

        self.assertEqual(sorted(self.firebase.tree), [f"RPI-2-{TODAY}", "stats"])

    def test_empty_firebase_deletes_nothing(self):
        self.use_tree({})

        with self.assertLogs(helpers.logger, "INFO") as logs:
            helpers.delete_all_by_entry_nodes()

        self.assertIn("No data found in Firebase.", logs.output[0])
        self.assertNotIn("delete", [call for call, path in self.firebase.calls])


class TestDeleteAllByNodes(FirebaseHelpersTestCase):
    def test_every_node_but_statistics_is_deleted(self):
        helpers.delete_all_by_nodes()

        self.assertEqual(self.firebase.tree, {"stats": STATS})

    def test_empty_firebase_deletes_nothing(self):
        self.use_tree({})

        helpers.delete_all_by_nodes()

        self.assertNotIn("delete", [call for call, path in self.firebase.calls])


class TestDeleteAllBySmallestNodes(FirebaseHelpersTestCase):
    def test_every_leaf_but_statistics_is_deleted(self):
        helpers.delete_all_by_smallest_nodes()

        self.assertEqual(self.firebase.tree, {"stats": STATS})

    def test_leaves_are_deleted_one_by_one(self):
        self.use_tree({f"RPI-1-{YESTERDAY}": {"data": {"e0": {"ssid": "CERN"}}}})

        helpers.delete_all_by_smallest_nodes()

        deletes = [path for call, path in self.firebase.calls if call == "delete"]
        self.assertEqual(deletes, [f"/RPI-1-{YESTERDAY}/data/e0/ssid"])

    def test_empty_firebase_deletes_nothing(self):
        self.use_tree({})

        helpers.delete_all_by_smallest_nodes()

        self.assertNotIn("delete", [call for call, path in self.firebase.calls])


if __name__ == "__main__":
    unittest.main()
