"""End-to-end test of the whole data pipeline, from captured Wi-Fi frames to database rows."""

import unittest
import uuid
from datetime import datetime, time, timedelta
from unittest import mock

from tests.integration.aggregator_db import AggregatorDatabaseMixin
from tests.integration.containers import (
    REDIS_DB_PIPELINE_CACHE,
    requires_postgres,
    requires_redis,
)
from tests.integration.test_collector_capture import (
    FILTERED_MAC,
    PARIS,
    CollectorCaptureTestCase,
)
from tests.support.aggregator_loader import (
    celery_eager_mode,
    import_aggregator_module,
)
from tests.support.probe_capture import beacon, probe_request

# Frames each device captures, by days ago. The aggregator imports the two days before today.
CAPTURES = {
    2: {
        "RPI-1": [
            ("probe", "00:1a:2b:00:00:01", b"CERN-Guest", {"frequency": 2412}),
            ("probe", "00:1a:2b:00:00:02", b"CERN-Guest", {"ds_channel": 6}),
            ("beacon", "aa:bb:cc:dd:ee:ff", b"Access point", {}),
        ],
        "RPI-2": [
            ("probe", "00:1a:2b:00:00:01", b"eduroam", {"frequency": 2462}),
            ("probe", FILTERED_MAC, b"eduroam", {"frequency": 2462}),
        ],
    },
    1: {
        "RPI-1": [("probe", "02:00:00:00:00:03", b"", {"frequency": 2437})],
    },
}

# What ends up in captured_info: (days ago, MAC, SSID, device, channel).
EXPECTED_ROWS = [
    (2, "00:1a:2b:00:00:01", "CERN-Guest", "RPI-1", 1),
    (2, "00:1a:2b:00:00:02", "CERN-Guest", "RPI-1", 6),
    (2, "00:1a:2b:00:00:01", "eduroam", "RPI-2", 11),
    (1, "02:00:00:00:00:03", "*", "RPI-1", 6),
]


@requires_postgres
@requires_redis
class TestCapturedFramesReachTheDatabase(
    AggregatorDatabaseMixin, CollectorCaptureTestCase
):
    database_prefix = "pipeline"
    cache_redis_db = REDIS_DB_PIPELINE_CACHE

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fastapi.testclient import TestClient

        cls.tasks = import_aggregator_module("aggregator.background.tasks")
        cls.celery_app = import_aggregator_module("aggregator.background.celery").celery
        cls.client = TestClient(import_aggregator_module("aggregator.main").app)

    def setUp(self):
        super().setUp()
        # The last import was three days ago, so the aggregator imports days 2 and 1.
        self.add(self.models.ImportsInfo(timestamp=self.today() - timedelta(days=3)))
        for target, name in (
            (self.tasks, "publish_message_to_channel"),
            (self.tasks, "publish_to_channel"),
        ):
            patcher = mock.patch.object(target, name)
            patcher.start()
            self.addCleanup(patcher.stop)
        # The queued Celery task runs before POST /aggregate answers.
        self.enterContext(celery_eager_mode(self.celery_app))

    def capture_all(self):
        for days_ago, devices in CAPTURES.items():
            day = self.today() - timedelta(days=days_ago)
            for device, frames in devices.items():
                packets = []
                for minute, (kind, mac, ssid, options) in enumerate(frames):
                    at = datetime.combine(day, time(10, minute), tzinfo=PARIS)
                    if kind == "probe":
                        packets.append(probe_request(mac, ssid, at=at, **options))
                    else:
                        packets.append(beacon(mac, ssid, at=at))
                self.capture(packets, device=device, day=day)

    def test_frames_captured_by_the_devices_end_up_in_the_database(self):
        self.capture_all()

        response = self.client.post("/aggregate")
        self.assertEqual(response.json()["status"], "ACCEPTED", response.json())
        workflow_id = response.json()["workflow_id"]

        status = self.client.get(f"/aggregate/{workflow_id}").json()["status"]
        self.assertEqual(status, "COMPLETED")

        rows = self.rows(
            "SELECT c.capture_date, m.mac, s.ssid, lm.device, c.channel "
            "FROM captured_info c "
            "JOIN mac m ON m.id = c.mac "
            "JOIN ssid s ON s.id = c.ssid "
            "JOIN location_mapping lm ON lm.location_id = c.location "
            "ORDER BY c.capture_date, lm.device, c.timestamp"
        )
        self.assertEqual(
            rows,
            [
                (self.today() - timedelta(days=days_ago), mac, ssid, device, channel)
                for days_ago, mac, ssid, device, channel in EXPECTED_ROWS
            ],
        )

        self.assertEqual(
            self.rows(
                "SELECT timestamp, captured FROM imports_info "
                "WHERE workflow_id::text = :id ORDER BY timestamp",
                id=workflow_id,
            ),
            [
                (self.today() - timedelta(days=2), 3),
                (self.today() - timedelta(days=1), 1),
            ],
        )
        uuid.UUID(workflow_id)  # The API returns a real workflow ID.


if __name__ == "__main__":
    unittest.main()
