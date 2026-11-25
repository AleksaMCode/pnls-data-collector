"""End-to-end tests of the aggregator import workflow on real services."""

import importlib
import json
import time
import unittest
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

from tests.integration.aggregator_db import AggregatorDatabaseMixin
from tests.integration.containers import (
    REDIS_DB_CELERY_BACKEND,
    REDIS_DB_CELERY_BROKER,
    REDIS_DB_WORKFLOW_CACHE,
    assert_firebase_is_emulator,
    connect_firebase_emulator,
    redis_url,
    requires_firebase,
    requires_postgres,
    requires_redis,
)
from tests.support.aggregator_loader import (
    import_aggregator_module,
    import_firebase_helpers,
    test_rsa_key,
)
from util.util import encrypt_data

SEED_FILE = Path(__file__).parent / "fixtures" / "aggregator_firebase_seed.json"
WORKER_TIMEOUT_SECONDS = 60

# What the seed imports: probe requests per date (days ago), and the rows they create.
EXPECTED_IMPORTS = {2: 4, 1: 2}
EXPECTED_SSIDS = {"CERN-Guest", "eduroam", "Home"}
EXPECTED_MAC_OUIS = {
    "00:1A:2B:00:00:01": "Example Org",
    "00:1A:2B:00:00:02": "Example Org",
    "02:00:00:00:00:03": None,  # Locally administered, not looked up.
    "F4:00:00:00:00:08": None,  # No IEEE assignment in the seed.
}

firebase_helpers = None
tasks = None
celery_app = None


def setUpModule():
    global firebase_helpers, tasks, celery_app
    firebase_helpers = import_firebase_helpers()
    tasks = import_aggregator_module("aggregator.background.tasks")
    celery_app = importlib.import_module("aggregator.background.celery").celery

    # Set before any task is sent, as Celery connects to the broker lazily.
    celery_app.conf.update(
        broker_url=redis_url(REDIS_DB_CELERY_BROKER),
        result_backend=redis_url(REDIS_DB_CELERY_BACKEND),
    )


@requires_postgres
@requires_redis
@requires_firebase
class WorkflowTestCase(AggregatorDatabaseMixin, unittest.TestCase):
    database_prefix = "aggregator_workflow"
    cache_redis_db = REDIS_DB_WORKFLOW_CACHE

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connect_firebase_emulator()
        cls.seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))

    def setUp(self):
        super().setUp()
        assert_firebase_is_emulator()
        self.seed_database()
        self.seed_firebase()

        key_patcher = mock.patch.object(firebase_helpers, "RSA_KEY", test_rsa_key())
        key_patcher.start()
        self.addCleanup(key_patcher.stop)

        self.messages = self.patch_tasks("publish_message_to_channel")
        self.summaries = self.patch_tasks("publish_to_channel")

    def patch_tasks(self, name, **kwargs):
        patcher = mock.patch.object(tasks, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def seed_database(self):
        models = self.models
        # The last import was three days ago, so two dates are pending.
        self.add(models.ImportsInfo(timestamp=self.today() - timedelta(days=3)))
        for index, entry in enumerate(self.seed["ieee"], start=1):
            self.add(models.IEEEMacOuiOrg(id=index, name=entry["org"]))
            self.add(
                models.IEEEMacOui(
                    id=index,
                    registry=entry["registry"],
                    assignment=entry["assignment"],
                    org=index,
                )
            )
        self.refresh_oui_view()

    def seed_firebase(self, extra_records: dict | None = None):
        public_key = test_rsa_key().publickey()
        tree = {}
        for node in self.seed["nodes"]:
            day = self.today() - timedelta(days=node["days_ago"])
            records = tree.setdefault(f"{node['device']}-{day}", {"data": {}})["data"]
            for record in node["records"]:
                records[f"r{len(records)}"] = {
                    "mac": encrypt_data(public_key, record["mac"]),
                    "ssid": record["ssid"],
                    "channel": record["channel"],
                    "timestamp": f"{day} {record['time']}",
                }
        for node_key, record in (extra_records or {}).items():
            records = tree.setdefault(node_key, {"data": {}})["data"]
            records[f"r{len(records)}"] = record
        firebase_helpers.db.reference("/").set(tree)

    def pending_dates(self) -> list[str]:
        return [
            (self.today() - timedelta(days=days_ago)).isoformat()
            for days_ago in sorted(EXPECTED_IMPORTS, reverse=True)
        ]

    def assert_seed_imported(self, workflow_id):
        self.assertEqual(
            self.rows(
                "SELECT timestamp, captured FROM imports_info "
                "WHERE workflow_id::text = :id ORDER BY timestamp",
                id=str(workflow_id),
            ),
            [
                (self.today() - timedelta(days=days_ago), count)
                for days_ago, count in sorted(EXPECTED_IMPORTS.items(), reverse=True)
            ],
        )
        self.assertEqual(
            self.scalar("SELECT count(*) FROM captured_info"),
            sum(EXPECTED_IMPORTS.values()),
        )
        self.assertEqual(
            {row[0] for row in self.rows("SELECT ssid FROM ssid")}, EXPECTED_SSIDS
        )
        self.assertEqual(
            dict(
                self.rows(
                    "SELECT m.mac, v.org FROM mac m "
                    "LEFT JOIN ieee_mac_oui_with_country v ON v.id = m.oui"
                )
            ),
            EXPECTED_MAC_OUIS,
        )

    def assert_workflow_finished(self, workflow_id, status: str):
        self.assertEqual(
            self.rows(
                'SELECT status::text, "end" IS NOT NULL FROM imports_workflow '
                "WHERE id::text = :id",
                id=str(workflow_id),
            ),
            [(status, True)],
        )
        self.assertEqual(
            json.loads(self.cache.get(str(workflow_id))), {"status": status}
        )


class TestImportWorkflowTask(WorkflowTestCase):
    def run_task(self, workflow_id):
        return tasks.import_workflow_task(str(workflow_id), self.pending_dates())

    def test_imports_every_pending_date(self):
        workflow_id = self.helpers.create_import_workflow()

        result = self.run_task(workflow_id)

        self.assertEqual(
            result, {"workflow_id": str(workflow_id), "status": "COMPLETED"}
        )
        self.assert_seed_imported(workflow_id)
        self.assert_workflow_finished(workflow_id, "COMPLETED")

    def test_announces_each_date_and_its_totals_on_mattermost(self):
        self.run_task(self.helpers.create_import_workflow())

        self.assertEqual(self.messages.call_count, len(EXPECTED_IMPORTS))
        counts = [call.args[1] for call in self.summaries.call_args_list]
        self.assertEqual(
            counts,
            [EXPECTED_IMPORTS[days] for days in sorted(EXPECTED_IMPORTS, reverse=True)],
        )
        self.assertEqual(
            self.summaries.call_args_list[-1].args[0],
            {"total_count": 6, "mac_count": 4, "ssid_count": 3},
        )

    def test_firebase_failure_marks_the_workflow_failed(self):
        workflow_id = self.helpers.create_import_workflow()

        with mock.patch.object(
            tasks,
            "fetch_data",
            side_effect=Exception("Import of Firebase data failed."),
        ):
            with self.assertRaisesRegex(Exception, "Import of Firebase data failed"):
                self.run_task(workflow_id)

        self.assert_workflow_finished(workflow_id, "FAILED")
        self.assertEqual(self.scalar("SELECT count(*) FROM captured_info"), 0)

    @unittest.expectedFailure
    def test_failed_import_marks_the_workflow_failed(self):
        """Known bug: import_data catches its own errors and returns 0, so a failed import is
        reported as COMPLETED. Remove the decorator once the failure reaches the task.
        """
        day = self.today() - timedelta(days=2)
        self.seed_firebase(
            {
                f"RPI-1-{day}": {
                    "mac": encrypt_data(
                        test_rsa_key().publickey(), "00:1A:2B:00:00:09"
                    ),
                    "ssid": "CERN",
                    "channel": 6,
                    "timestamp": "not a timestamp",
                }
            }
        )
        workflow_id = self.helpers.create_import_workflow()

        try:
            self.run_task(workflow_id)
        except Exception:
            pass  # Once fixed, the task re-raises like any other failed workflow.
        self.assert_workflow_finished(workflow_id, "FAILED")


class ApiTestCase(WorkflowTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fastapi.testclient import TestClient

        cls.main = import_aggregator_module("aggregator.main")
        cls.client = TestClient(cls.main.app)

    def start_aggregation(self) -> str:
        response = self.client.post("/aggregate")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "ACCEPTED", response.json())
        return response.json()["workflow_id"]

    def workflow_status(self, workflow_id: str):
        response = self.client.get(f"/aggregate/{workflow_id}")
        self.assertEqual(response.status_code, 200, response.json())
        return response.json()["status"]


class TestAggregateApi(ApiTestCase):
    """POST /aggregate with Celery in eager mode: the queued task runs before the response."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(celery_app.conf, "task_always_eager", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_full_import_through_the_api(self):
        workflow_id = self.start_aggregation()

        self.assertEqual(self.workflow_status(workflow_id), "COMPLETED")
        self.assert_seed_imported(uuid.UUID(workflow_id))
        self.assert_workflow_finished(workflow_id, "COMPLETED")

    def test_next_call_finds_the_imports_up_to_date(self):
        self.start_aggregation()

        response = self.client.post("/aggregate")

        self.assertEqual(response.json()["status"], "SKIPPED")

    def test_status_falls_back_to_the_database_after_redis_expiry(self):
        workflow_id = self.start_aggregation()
        self.cache.delete(workflow_id)

        self.assertEqual(self.workflow_status(workflow_id), "COMPLETED")

    def test_unknown_workflow_is_not_found(self):
        response = self.client.get(f"/aggregate/{uuid.uuid4()}")

        self.assertEqual(response.status_code, 404)


class TestAggregateApiWithWorker(ApiTestCase):
    """POST /aggregate with a real Celery worker, as in production: the task goes through the
    Redis broker, and the client polls the status endpoint until the workflow finishes.
    """

    def test_full_import_through_the_broker(self):
        from celery.contrib.testing.worker import start_worker

        with start_worker(
            celery_app, pool="solo", perform_ping_check=False, loglevel="WARNING"
        ):
            workflow_id = self.start_aggregation()
            status = self.wait_for_final_status(workflow_id)

        self.assertEqual(status, "COMPLETED")
        self.assert_seed_imported(uuid.UUID(workflow_id))

    def wait_for_final_status(self, workflow_id: str) -> str:
        deadline = time.monotonic() + WORKER_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            status = self.workflow_status(workflow_id)
            if status != "STARTED":
                return status
            time.sleep(0.5)
        self.fail(
            f"Workflow {workflow_id} did not finish in {WORKER_TIMEOUT_SECONDS}s."
        )


if __name__ == "__main__":
    unittest.main()
