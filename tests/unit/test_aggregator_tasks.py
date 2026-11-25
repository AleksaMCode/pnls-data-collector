"""Unit tests for the aggregator Celery task and the Celery connection settings."""

import importlib
import json
import os
import unittest
import uuid
from datetime import date, timedelta
from unittest import mock

from tests.support.aggregator_loader import import_aggregator_module

tasks = import_aggregator_module("aggregator.background.tasks")
celery_module = importlib.import_module("aggregator.background.celery")
WorkflowStatus = tasks.WorkflowStatus

WORKFLOW_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TasksMixin:
    def patch_task(self, name, **kwargs):
        patcher = mock.patch.object(tasks, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched


class TestTransferData(TasksMixin, unittest.TestCase):
    def setUp(self):
        self.fetch_data = self.patch_task("fetch_data", return_value=["record"])
        self.import_data = self.patch_task("import_data", return_value=7)
        self.get_totals = self.patch_task("get_totals", return_value={"totals": 1})
        self.publish = self.patch_task("publish_to_channel")

    def test_imports_one_date_and_publishes_the_totals(self):
        day = date(2026, 6, 14)

        tasks.transfer_data(day, WORKFLOW_ID)

        self.fetch_data.assert_called_once_with(day)
        self.import_data.assert_called_once_with(
            ["record"],
            firebase_import=True,
            manual_import_date=day,
            workflow_id=WORKFLOW_ID,
        )
        self.publish.assert_called_once_with({"totals": 1}, 7, day)

    def test_failed_mattermost_message_does_not_fail_the_import(self):
        self.publish.side_effect = ConnectionError("Mattermost down")

        tasks.transfer_data(date(2026, 6, 14), WORKFLOW_ID)

        self.import_data.assert_called_once()

    def test_firebase_error_stops_the_transfer(self):
        self.fetch_data.side_effect = Exception("Import of Firebase data failed.")

        with self.assertRaisesRegex(Exception, "Import of Firebase data failed"):
            tasks.transfer_data(date(2026, 6, 14), WORKFLOW_ID)
        self.import_data.assert_not_called()


class TestTransferDataAll(TasksMixin, unittest.TestCase):
    def setUp(self):
        self.transfer = self.patch_task("transfer_data")
        self.message = self.patch_task("publish_message_to_channel")

    def test_nothing_to_import(self):
        tasks.transfer_data_all([], WORKFLOW_ID)

        self.transfer.assert_not_called()
        self.message.assert_not_called()

    def test_every_date_is_announced_and_imported_in_order(self):
        days = [date(2026, 6, 13), date(2026, 6, 14)]

        tasks.transfer_data_all(days, WORKFLOW_ID)

        self.assertEqual(
            self.transfer.call_args_list,
            [mock.call(day, WORKFLOW_ID) for day in days],
        )
        self.assertEqual(
            [call.args[0] for call in self.message.call_args_list],
            [f"Transfer data from {day} workflow started." for day in days],
        )

    def test_failed_date_stops_the_remaining_dates(self):
        self.transfer.side_effect = [Exception("first date failed"), None]

        with self.assertRaisesRegex(Exception, "first date failed"):
            tasks.transfer_data_all([date(2026, 6, 13), date(2026, 6, 14)], WORKFLOW_ID)
        self.transfer.assert_called_once()


class TestImportWorkflowTask(TasksMixin, unittest.TestCase):
    def setUp(self):
        self.transfer_all = self.patch_task("transfer_data_all")
        self.set_status = self.patch_task("set_import_workflow_status")
        self.set_key = self.patch_task("set_key_value")

    def run_task(self):
        # Calling a Celery task runs it in this process, without a broker.
        return tasks.import_workflow_task(
            str(WORKFLOW_ID), ["2026-06-13", "2026-06-14"]
        )

    def test_parses_the_arguments_sent_through_the_broker(self):
        self.run_task()

        self.transfer_all.assert_called_once_with(
            [date(2026, 6, 13), date(2026, 6, 14)], WORKFLOW_ID
        )

    def test_success_marks_the_workflow_completed(self):
        result = self.run_task()

        self.assertEqual(
            result, {"workflow_id": str(WORKFLOW_ID), "status": "COMPLETED"}
        )
        self.set_status.assert_called_once_with(WORKFLOW_ID, WorkflowStatus.COMPLETED)
        self.set_key.assert_called_once_with(
            str(WORKFLOW_ID),
            json.dumps({"status": "COMPLETED"}),
            ttl=tasks.WORKFLOW_FINAL_STATUS_TTL_SECONDS,
        )

    def test_failure_marks_the_workflow_failed_and_reraises(self):
        self.transfer_all.side_effect = RuntimeError("import failed")

        with self.assertRaises(RuntimeError):
            self.run_task()

        self.set_status.assert_called_once_with(WORKFLOW_ID, WorkflowStatus.FAILED)
        self.set_key.assert_called_once_with(
            str(WORKFLOW_ID),
            json.dumps({"status": "FAILED"}),
            ttl=tasks.WORKFLOW_FINAL_STATUS_TTL_SECONDS,
        )

    def test_invalid_workflow_id_is_rejected_before_any_import(self):
        with self.assertRaises(ValueError):
            tasks.import_workflow_task("not-a-uuid", ["2026-06-14"])
        self.transfer_all.assert_not_called()


class TestCeleryConnection(unittest.TestCase):
    def env(self, **values):
        keys = ("REDIS_PASSWORD", "REDIS_URL", "REDIS_PORT")
        environment = {k: v for k, v in os.environ.items() if k not in keys}
        environment.update(values)
        return mock.patch.dict(os.environ, environment, clear=True)

    def test_url_without_password(self):
        with self.env():
            self.assertEqual(
                celery_module._redis_connection_url(0), "redis://redis:6379/0"
            )

    def test_url_with_password_host_and_port(self):
        with self.env(REDIS_PASSWORD="secret", REDIS_URL="cache", REDIS_PORT="6380"):
            self.assertEqual(
                celery_module._redis_connection_url(1), "redis://:secret@cache:6380/1"
            )

    def test_empty_password_adds_no_credentials(self):
        with self.env(REDIS_PASSWORD=""):
            self.assertEqual(celery_module._redis_auth(), "")

    def test_app_settings(self):
        app = celery_module.celery

        self.assertEqual(app.main, "aggregator")
        self.assertIn("aggregator.background.tasks", app.conf.include)
        self.assertEqual(app.conf.result_expires, timedelta(days=10))
        self.assertIn("aggregator.import_workflow", app.tasks)


if __name__ == "__main__":
    unittest.main()
