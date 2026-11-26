"""Unit tests for the housekeeping MongoDB backup, with GridFS and the collections replaced."""

import json
import unittest
from datetime import datetime
from unittest import mock

from tests.support.housekeeping_loader import import_housekeeping_module

helpers = import_housekeeping_module("firebase_housekeeping.core.mongo.helpers")

TODAY = datetime(2026, 6, 15, 5, 0)
BACKUP = {
    "RPI-1": [{"data": {"e0": {"ssid": "CERN"}}}],
    "RPI-2": [{"data": {"e1": {"ssid": "eduroam"}}}, {"data": {}}],
}


class FixedClock(datetime):
    @classmethod
    def today(cls):
        return TODAY


class MongoHelpersTestCase(unittest.TestCase):
    def setUp(self):
        self.bucket = mock.Mock()
        self.bucket.upload_from_stream.side_effect = self.record_upload
        self.uploads = {}
        self.collection = mock.Mock()
        for name, value in (
            ("get_bucket_for_write", mock.Mock(return_value=self.bucket)),
            ("get_bucket_for_read", mock.Mock(return_value=self.bucket)),
            ("get_collection", mock.Mock(return_value=self.collection)),
            ("datetime", FixedClock),
            ("TIMESTAMP_FORMAT", "%Y-%m-%d %H:%M:%S.%f"),
        ):
            patcher = mock.patch.object(helpers, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def record_upload(self, filename, stream):
        self.uploads[filename] = json.loads(stream.read())
        return f"id-{filename}"


class TestInsertFromFirebaseToMongo(MongoHelpersTestCase):
    def test_one_file_per_device_named_by_the_day(self):
        helpers.insert_from_firebase_to_mongo(BACKUP)

        self.assertEqual(sorted(self.uploads), ["RPI-1-2026-06-15", "RPI-2-2026-06-15"])

    def test_each_file_holds_the_device_nodes_as_json(self):
        helpers.insert_from_firebase_to_mongo(BACKUP)

        self.assertEqual(self.uploads["RPI-1-2026-06-15"], BACKUP["RPI-1"])
        self.assertEqual(self.uploads["RPI-2-2026-06-15"], BACKUP["RPI-2"])

    def test_upload_is_logged_with_its_id(self):
        with self.assertLogs(helpers.logger, "INFO") as logs:
            helpers.insert_from_firebase_to_mongo({"RPI-1": BACKUP["RPI-1"]})

        self.assertIn("id=id-RPI-1-2026-06-15", logs.output[0])

    def test_unknown_device_is_logged_and_the_others_are_uploaded(self):
        with self.assertLogs(helpers.logger, "ERROR"):
            helpers.insert_from_firebase_to_mongo({"RPI-9": [], **BACKUP})

        self.assertEqual(sorted(self.uploads), ["RPI-1-2026-06-15", "RPI-2-2026-06-15"])

    def test_failed_upload_is_logged_and_the_others_are_uploaded(self):
        def fail_for_rpi_1(filename, stream):
            if filename.startswith("RPI-1"):
                raise ConnectionError("MongoDB is unreachable")
            return self.record_upload(filename, stream)

        self.bucket.upload_from_stream.side_effect = fail_for_rpi_1

        with self.assertLogs(helpers.logger, "ERROR") as logs:
            helpers.insert_from_firebase_to_mongo(BACKUP)

        self.assertIn("MongoDB is unreachable", logs.output[0])
        self.assertEqual(sorted(self.uploads), ["RPI-2-2026-06-15"])

    def test_nothing_to_back_up_uploads_nothing(self):
        helpers.insert_from_firebase_to_mongo({})

        self.bucket.upload_from_stream.assert_not_called()


class TestReadFirebaseDataFromMongo(MongoHelpersTestCase):
    def test_file_is_read_by_name(self):
        self.bucket.open_download_stream_by_name.return_value.read.return_value = (
            json.dumps(BACKUP["RPI-1"]).encode()
        )

        with self.assertLogs(helpers.logger, "INFO") as logs:
            helpers.read_firebase_data_from_mongo("RPI-1-2026-06-15")

        self.bucket.open_download_stream_by_name.assert_called_once_with(
            filename="RPI-1-2026-06-15"
        )
        self.assertIn("Successfully read file", logs.output[0])

    def test_missing_file_is_logged(self):
        self.bucket.open_download_stream_by_name.side_effect = FileNotFoundError(
            "no file"
        )

        with self.assertLogs(helpers.logger, "ERROR") as logs:
            helpers.read_firebase_data_from_mongo("RPI-1-2026-06-15")

        self.assertIn("no file", logs.output[0])

    def test_empty_stream_is_logged(self):
        self.bucket.open_download_stream_by_name.return_value = None

        with self.assertLogs(helpers.logger, "WARNING") as logs:
            helpers.read_firebase_data_from_mongo("RPI-1-2026-06-15")

        self.assertIn("No file found", logs.output[0])

    def test_every_stored_file_is_read(self):
        self.bucket.list.return_value = ["RPI-1-2026-06-15", "RPI-2-2026-06-15"]

        with mock.patch.object(helpers, "read_firebase_data_from_mongo") as read:
            helpers.read_all_firebase_data_from_mongo()

        self.assertEqual(
            [call.args[0] for call in read.call_args_list],
            ["RPI-1-2026-06-15", "RPI-2-2026-06-15"],
        )


class TestCollectionInserts(MongoHelpersTestCase):
    def test_insert_many_inserts_into_the_named_collection(self):
        helpers.insert_many([{"a": 1}, {"a": 2}], "captures")

        helpers.get_collection.assert_called_once_with("captures")
        self.collection.insert_many.assert_called_once_with([{"a": 1}, {"a": 2}])

    def test_unacknowledged_insert_is_logged(self):
        self.collection.insert_many.return_value.acknowledged = False

        with self.assertLogs(helpers.logger, "ERROR"):
            helpers.insert_many([{"a": 1}], "captures")

    def test_failed_insert_into_collection_is_logged_not_raised(self):
        self.collection.insert_many.side_effect = ConnectionError("down")

        with self.assertLogs(helpers.logger, "ERROR") as logs:
            helpers.insert_data_into_collection([{"a": 1}], "captures")

        self.assertIn("down", logs.output[-1])

    @unittest.expectedFailure
    def test_insert_one_inserts_one_document(self):
        """Known bug: insert_one calls insert_many. Remove the decorator once it calls insert_one."""
        helpers.insert_one({"a": 1}, "captures")

        self.collection.insert_one.assert_called_once_with({"a": 1})


if __name__ == "__main__":
    unittest.main()
