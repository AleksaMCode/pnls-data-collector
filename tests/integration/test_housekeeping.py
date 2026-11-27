"""Integration and end-to-end tests of Firebase housekeeping on the Firebase emulator and a real MongoDB."""

import json
import unittest
from datetime import UTC, datetime
from unittest import mock

from tests.integration.containers import (
    assert_firebase_is_emulator,
    connect_firebase_emulator,
    create_mongo_database,
    requires_firebase,
    requires_mongo,
)
from tests.support.aggregator_loader import no_retry_wait
from tests.support.fake_http import FakeMattermost, start_in_background, unused_port
from tests.support.housekeeping_loader import import_housekeeping_module

firebase_helpers = import_housekeeping_module(
    "firebase_housekeeping.core.firebase.helpers"
)
mongo_helpers = import_housekeeping_module("firebase_housekeeping.core.mongo.helpers")
main = import_housekeeping_module("firebase_housekeeping.main")
mattermost = import_housekeeping_module("util.mattermost.helpers")

# 23:30 UTC on June 14 is already June 15 in Paris (CEST), the collectors' time zone.
NOW_UTC = datetime(2026, 6, 14, 23, 30, tzinfo=UTC)
TODAY = "2026-06-15"
YESTERDAY = "2026-06-14"
STATS = {"devices": {"RPI-1": {"count": 3}}, "total_count": 3}


def entries(count: int, prefix: str) -> dict:
    return {
        f"{prefix}{index}": {
            "mac": f"ZW5j{prefix}{index}",
            "ssid": "CERN",
            "channel": 6,
            "timestamp": f"{YESTERDAY} 10:00:0{index}.000",
        }
        for index in range(count)
    }


def seed_tree() -> dict:
    return {
        "stats": STATS,
        f"RPI-1-{YESTERDAY}": {
            "data": entries(3, "a"),
            "status": {"status": "working", "timestamp": f"{YESTERDAY} 22:00:00.000"},
        },
        f"RPI-2-{YESTERDAY}": {"data": entries(2, "b")},
        f"RPI-2-{TODAY}": {"data": entries(1, "c")},
    }


# The statistics node is no longer used, so it's deleted with the rest.
AFTER_HOUSEKEEPING = {f"RPI-2-{TODAY}": seed_tree()[f"RPI-2-{TODAY}"]}


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW_UTC.astimezone(tz)

    @classmethod
    def today(cls):
        return datetime(2026, 6, 15, 5, 0)


class HousekeepingTestCase(unittest.TestCase):
    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)


@requires_firebase
class FirebaseTestCase(HousekeepingTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connect_firebase_emulator()

    def setUp(self):
        super().setUp()
        assert_firebase_is_emulator()
        self.root = firebase_helpers.db.reference("/")
        self.root.set(seed_tree())
        for name, value in (
            ("datetime", FixedClock),
            ("TIMEZONE", "Europe/Paris"),
            ("FIREBASE_STATISTICS_NODE", "stats"),
        ):
            self.patch(firebase_helpers, name, value)
        self.enterContext(no_retry_wait(firebase_helpers.delete_all_by_entry_nodes))

    def firebase(self) -> dict:
        return self.root.get() or {}


@requires_mongo
class MongoTestCase(HousekeepingTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import gridfs

        cls.mongo = create_mongo_database("housekeeping")
        cls.gridfs = gridfs
        cls.addClassCleanup(cls.mongo.client.drop_database, cls.mongo.name)

    def setUp(self):
        super().setUp()
        for name in self.mongo.list_collection_names():
            self.mongo.drop_collection(name)
        for name, value in (
            ("get_bucket_for_write", lambda: self.gridfs.GridFSBucket(self.mongo)),
            ("get_bucket_for_read", lambda: self.gridfs.GridFS(self.mongo)),
            ("get_collection", lambda collection: self.mongo[collection]),
            ("datetime", FixedClock),
        ):
            self.patch(mongo_helpers, name, value)

    def backup(self, filename: str):
        stream = self.gridfs.GridFSBucket(self.mongo).open_download_stream_by_name(
            filename
        )
        return json.loads(stream.read())

    def backup_names(self) -> list[str]:
        return sorted(self.gridfs.GridFS(self.mongo).list())


class TestFirebaseHelpersOnTheEmulator(FirebaseTestCase):
    def test_download_returns_every_device_node(self):
        data = firebase_helpers.download_all()

        tree = seed_tree()
        self.assertEqual(
            dict(data),
            {
                "RPI-1": [tree[f"RPI-1-{YESTERDAY}"]],
                "RPI-2": [tree[f"RPI-2-{YESTERDAY}"], tree[f"RPI-2-{TODAY}"]],
            },
        )

    def test_delete_by_entry_nodes_keeps_only_today(self):
        firebase_helpers.delete_all_by_entry_nodes()

        self.assertEqual(self.firebase(), AFTER_HOUSEKEEPING)

    def test_failed_bulk_delete_falls_back_to_batches_on_the_emulator(self):
        self.patch(firebase_helpers, "BULK_DELETE_SIZE", 1)
        real_reference = firebase_helpers.db.reference
        bulk_path = f"/RPI-1-{YESTERDAY}/data"

        def reference(path="/"):
            ref = real_reference(path)
            if path == bulk_path:
                ref.delete = mock.Mock(side_effect=RuntimeError("Payload too large"))
            return ref

        with mock.patch.object(firebase_helpers.db, "reference", reference):
            firebase_helpers.delete_all_by_entry_nodes()

        self.assertEqual(self.firebase(), AFTER_HOUSEKEEPING)

    def test_delete_by_nodes_deletes_everything(self):
        firebase_helpers.delete_all_by_nodes()

        self.assertEqual(self.firebase(), {})

    def test_delete_by_smallest_nodes_deletes_everything(self):
        firebase_helpers.delete_all_by_smallest_nodes()

        self.assertEqual(self.firebase(), {})


class TestMongoHelpersOnMongo(MongoTestCase):
    def test_backup_files_hold_the_firebase_nodes(self):
        tree = seed_tree()
        data = {
            "RPI-1": [tree[f"RPI-1-{YESTERDAY}"]],
            "RPI-2": [tree[f"RPI-2-{YESTERDAY}"]],
        }

        mongo_helpers.insert_from_firebase_to_mongo(data)

        self.assertEqual(self.backup_names(), ["RPI-1-2026-06-15", "RPI-2-2026-06-15"])
        self.assertEqual(self.backup("RPI-1-2026-06-15"), data["RPI-1"])
        self.assertEqual(self.backup("RPI-2-2026-06-15"), data["RPI-2"])

    def test_backup_file_can_be_read_back(self):
        mongo_helpers.insert_from_firebase_to_mongo({"RPI-1": [{"data": {}}]})

        with self.assertLogs(mongo_helpers.logger, "INFO") as logs:
            mongo_helpers.read_all_firebase_data_from_mongo()

        self.assertIn(
            "Successfully read file with filename RPI-1-2026-06-15.", logs.output[0]
        )

    def test_missing_backup_file_is_logged(self):
        with self.assertLogs(mongo_helpers.logger, "ERROR"):
            mongo_helpers.read_firebase_data_from_mongo("RPI-1-2026-06-15")

    def test_documents_are_inserted_into_a_collection(self):
        mongo_helpers.insert_data_into_collection(
            [{"ssid": "CERN"}, {"ssid": "eduroam"}], "captures"
        )

        self.assertEqual(
            sorted(doc["ssid"] for doc in self.mongo["captures"].find()),
            ["CERN", "eduroam"],
        )


class TestHousekeepingEndToEnd(FirebaseTestCase, MongoTestCase):
    """DELETE /delete on the emulator and MongoDB, with the real Mattermost webhook code."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import requests
        from fastapi.testclient import TestClient

        cls.requests = requests
        cls.mattermost = FakeMattermost()
        start_in_background(cls.mattermost, cls)
        cls.client = TestClient(main.app, raise_server_exceptions=False)

    def setUp(self):
        super().setUp()
        self.mattermost.messages.clear()
        self.patch(main, "MONGO_BACKUP", True)
        self.patch(main, "SLACK_WEBHOOK_URL", self.mattermost.url)
        # Under ENV=test, util.mattermost.helpers does not import requests.
        patcher = mock.patch.object(mattermost, "requests", self.requests, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_firebase_is_backed_up_to_mongo_then_cleaned(self):
        response = self.client.delete("/delete")

        self.assertEqual(response.status_code, 200)
        tree = seed_tree()
        self.assertEqual(self.backup_names(), ["RPI-1-2026-06-15", "RPI-2-2026-06-15"])
        self.assertEqual(self.backup("RPI-1-2026-06-15"), [tree[f"RPI-1-{YESTERDAY}"]])
        self.assertEqual(
            self.backup("RPI-2-2026-06-15"),
            [tree[f"RPI-2-{YESTERDAY}"], tree[f"RPI-2-{TODAY}"]],
        )
        self.assertEqual(self.firebase(), AFTER_HOUSEKEEPING)

    def test_start_and_end_are_posted_to_mattermost(self):
        self.client.delete("/delete")

        self.assertEqual(
            [
                (message["username"], message["text"])
                for message in self.mattermost.messages
            ],
            [
                ("Housekeeping", "Firebase delete workflow started."),
                ("Housekeeping", "Firebase delete workflow completed."),
            ],
        )

    @unittest.expectedFailure
    def test_firebase_is_kept_when_mongo_is_unreachable(self):
        """Known bug: the failed upload is only logged, and Firebase is deleted without a backup.
        Remove the decorator once a failed backup stops the delete.
        """
        import gridfs
        import pymongo

        unreachable = pymongo.MongoClient(
            f"mongodb://127.0.0.1:{unused_port()}", serverSelectionTimeoutMS=500
        )
        self.addCleanup(unreachable.close)
        self.patch(
            mongo_helpers,
            "get_bucket_for_write",
            lambda: gridfs.GridFSBucket(unreachable["housekeeping"]),
        )

        self.client.delete("/delete")

        self.assertEqual(self.firebase(), seed_tree())


if __name__ == "__main__":
    unittest.main()
