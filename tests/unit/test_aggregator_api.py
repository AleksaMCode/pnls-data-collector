"""Unit tests for the aggregator API, with the database, Redis and Celery calls mocked."""

import json
import unittest
import uuid
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from tests.support.aggregator_loader import import_aggregator_module

main = import_aggregator_module("aggregator.main")
WorkflowStatus = main.WorkflowStatus

WORKFLOW_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def today():
    return datetime.now(ZoneInfo(main.TIMEZONE)).date()


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        # Entering the client runs the app's lifespan (startup and shutdown).
        self.client = self.enterContext(TestClient(main.app))

    def patch_main(self, name, **kwargs):
        patcher = mock.patch.object(main, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched


class TestStartAggregation(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.running = self.patch_main(
            "get_running_import_workflow_id", return_value=None
        )
        self.latest = self.patch_main(
            "get_latest_import_date", return_value=today() - timedelta(days=3)
        )
        self.create = self.patch_main(
            "create_import_workflow", return_value=WORKFLOW_ID
        )
        self.set_key = self.patch_main("set_key_value")
        self.task = self.patch_main("import_workflow_task")
        self.task.delay.return_value.id = "task-1"

    def test_queues_a_workflow_for_every_pending_date(self):
        response = self.client.post("/aggregate")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json(),
            {
                "status": "ACCEPTED",
                "workflow_id": str(WORKFLOW_ID),
                "task_id": "task-1",
                "message": "Data aggregation workflow queued.",
            },
        )
        self.task.delay.assert_called_once_with(
            str(WORKFLOW_ID),
            [(today() - timedelta(days=n)).isoformat() for n in (2, 1)],
        )

    def test_stores_the_started_status_in_redis(self):
        self.client.post("/aggregate")

        self.set_key.assert_called_once_with(
            str(WORKFLOW_ID),
            json.dumps({"status": "STARTED"}),
            ttl=main.WORKFLOW_STARTED_STATUS_TTL_SECONDS,
        )

    def test_returns_the_running_workflow_instead_of_starting_another(self):
        self.running.return_value = WORKFLOW_ID

        response = self.client.post("/aggregate")

        self.assertEqual(response.json()["status"], "ACCEPTED")
        self.assertEqual(response.json()["workflow_id"], str(WORKFLOW_ID))
        self.assertIsNone(response.json()["task_id"])
        self.create.assert_not_called()
        self.task.delay.assert_not_called()

    def test_skips_when_imports_are_up_to_date(self):
        self.latest.return_value = today() - timedelta(days=1)

        response = self.client.post("/aggregate")

        self.assertEqual(response.json()["status"], "SKIPPED")
        self.create.assert_not_called()
        self.task.delay.assert_not_called()

    def test_reports_an_error_when_the_workflow_cannot_be_created(self):
        self.create.return_value = None

        response = self.client.post("/aggregate")

        # The endpoint always answers 202; the outcome is in the body.
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "ERROR")
        self.set_key.assert_not_called()
        self.task.delay.assert_not_called()


class TestWorkflowStatus(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.get_key = self.patch_main("get_key_value", return_value=None)
        self.db_status = self.patch_main(
            "get_import_workflow_status", return_value=None
        )

    def get(self, workflow_id=str(WORKFLOW_ID)):
        return self.client.get(f"/aggregate/{workflow_id}")

    def test_reads_the_status_from_redis_first(self):
        self.get_key.return_value = json.dumps({"status": "STARTED"})

        response = self.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"workflow_id": str(WORKFLOW_ID), "status": "STARTED"}
        )
        self.db_status.assert_not_called()

    def test_broken_redis_payload_is_a_server_error(self):
        for payload in ("not json", json.dumps({"state": "STARTED"})):
            with self.subTest(payload=payload):
                self.get_key.return_value = payload

                self.assertEqual(self.get().status_code, 500)

    def test_falls_back_to_the_database(self):
        self.db_status.return_value = WorkflowStatus.COMPLETED

        response = self.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "COMPLETED")
        self.db_status.assert_called_once_with(WORKFLOW_ID)

    def test_invalid_workflow_id_is_a_bad_request(self):
        response = self.get("not-a-uuid")

        self.assertEqual(response.status_code, 400)
        self.db_status.assert_not_called()

    def test_unknown_workflow_is_not_found(self):
        self.assertEqual(self.get().status_code, 404)


if __name__ == "__main__":
    unittest.main()
