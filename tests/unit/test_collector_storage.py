"""Unit tests for where the collector stores records: Firebase and the local backup file."""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from tests.support.collector_loader import import_collector_module

firebase = import_collector_module("collector.core.firebase.helpers")
backup = import_collector_module("collector.util.util")

RECORD = {
    "mac": "ZW5jcnlwdGVk",
    "ssid": "CERN",
    "channel": 6,
    "timestamp": "2026-06-14 10:15:30.123",
}


class TestFirebase(unittest.TestCase):
    def setUp(self):
        for name, value in (("FIREBASE_NODE", "RPI-2"), ("TIMEZONE", "Europe/Paris")):
            patcher = mock.patch.object(firebase, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(firebase, "db")
        self.db = patcher.start()
        self.addCleanup(patcher.stop)

    def test_record_is_pushed_under_the_node_of_the_day(self):
        firebase.publish_captured_date(RECORD, "2026-06-14")

        self.db.reference.assert_called_once_with("/RPI-2-2026-06-14/data")
        self.db.reference.return_value.push.assert_called_once_with(RECORD)

    def test_status_is_written_in_the_collector_time_zone(self):
        # 23:59:59.5 UTC on June 14 is already June 15 in Paris (CEST).
        utc_now = datetime(2026, 6, 14, 23, 59, 59, 500000, tzinfo=UTC)

        class FixedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_now.astimezone(tz)

        with mock.patch.object(firebase, "datetime", FixedClock):
            firebase.update_device_status()

        self.db.reference.assert_called_once_with("/RPI-2-2026-06-15/status")
        self.db.reference.return_value.update.assert_called_once_with(
            {"status": "working", "timestamp": "2026-06-15 01:59:59.500000"}
        )


class TestLocalBackup(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        patcher = mock.patch.object(backup, "DATA_DIR", str(self.folder))
        patcher.start()
        self.addCleanup(patcher.stop)

    def lines(self, file_name: str) -> list[dict]:
        text = (self.folder / file_name).read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def test_records_are_appended_one_json_line_each(self):
        second = dict(RECORD, ssid="eduroam")

        backup.publish_captured_data_locally(RECORD, "2026-06-14")
        backup.publish_captured_data_locally(second, "2026-06-14")

        self.assertEqual(self.lines("2026-06-14-data.json"), [RECORD, second])

    def test_each_day_has_its_own_file(self):
        backup.publish_captured_data_locally(RECORD, "2026-06-14")
        backup.publish_captured_data_locally(RECORD, "2026-06-15")

        self.assertEqual(
            sorted(path.name for path in self.folder.iterdir()),
            ["2026-06-14-data.json", "2026-06-15-data.json"],
        )

    def test_non_ascii_ssid_is_kept(self):
        record = dict(RECORD, ssid="Café ☕")

        backup.publish_captured_data_locally(record, "2026-06-14")

        self.assertEqual(self.lines("2026-06-14-data.json")[0]["ssid"], "Café ☕")


if __name__ == "__main__":
    unittest.main()
