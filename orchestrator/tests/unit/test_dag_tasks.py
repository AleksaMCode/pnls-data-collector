"""Unit tests for the functions that the orchestrator DAG tasks call."""

import json
import os
import unittest
from datetime import UTC, date, datetime
from unittest import mock

import httpx

from orchestrator.tests.dag_loader import load_dag_module, load_fresh_dag_module

dag_module = load_dag_module()
AirflowException = dag_module.AirflowException


def make_context(xcom_value=None, logical_date=None) -> dict:
    """Builds the part of the Airflow task context that the callables read."""
    ti = mock.MagicMock(name="ti")
    ti.xcom_pull.return_value = xcom_value
    return {
        "ti": ti,
        "logical_date": logical_date or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    }


class RequestServiceMixin:
    """Replaces `_request_service`, which every task uses for its HTTP calls."""

    def patch_request_service(self, return_value=None, side_effect=None):
        patcher = mock.patch.object(
            dag_module,
            "_request_service",
            return_value=return_value,
            side_effect=side_effect,
        )
        request_service = patcher.start()
        self.addCleanup(patcher.stop)
        return request_service


class TestRequestService(unittest.TestCase):
    """Tests the HTTP helper with an in-memory httpx transport, so no request leaves the process."""

    def setUp(self):
        self.sent_requests: list[httpx.Request] = []

    def patch_transport(self, handler):
        def recording_handler(request: httpx.Request) -> httpx.Response:
            self.sent_requests.append(request)
            return handler(request)

        patcher = mock.patch.object(
            dag_module.httpx,
            "HTTPTransport",
            return_value=httpx.MockTransport(recording_handler),
        )
        transport_class = patcher.start()
        self.addCleanup(patcher.stop)
        return transport_class

    def test_returns_parsed_json_body(self):
        self.patch_transport(lambda _: httpx.Response(200, json={"status": "ok"}))

        result = dag_module._request_service("GET", "http://service.test/health")

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(self.sent_requests[0].method, "GET")
        self.assertEqual(str(self.sent_requests[0].url), "http://service.test/health")

    def test_json_content_type_with_charset_is_parsed(self):
        self.patch_transport(
            lambda _: httpx.Response(
                200,
                content=b'{"a": 1}',
                headers={"content-type": "application/json; charset=utf-8"},
            )
        )

        self.assertEqual(
            dag_module._request_service("GET", "http://service.test"), {"a": 1}
        )

    def test_wraps_non_json_body_in_raw_response(self):
        self.patch_transport(lambda _: httpx.Response(200, text="wf-123"))

        result = dag_module._request_service("POST", "http://service.test/start")

        self.assertEqual(result, {"raw_response": "wf-123"})

    def test_sends_json_payload(self):
        self.patch_transport(lambda _: httpx.Response(200, json={}))

        dag_module._request_service(
            "POST", "http://service.test", json_payload={"key": "value"}
        )

        request = self.sent_requests[0]
        self.assertEqual(json.loads(request.content), {"key": "value"})
        self.assertIn("application/json", request.headers["content-type"])

    def test_sends_no_body_without_payload(self):
        self.patch_transport(lambda _: httpx.Response(200, json={}))

        dag_module._request_service("DELETE", "http://service.test/delete")

        self.assertEqual(self.sent_requests[0].content, b"")

    def test_uses_default_timeout(self):
        self.patch_transport(lambda _: httpx.Response(200, json={}))

        with mock.patch.object(dag_module, "REQUEST_TIMEOUT_SECONDS", 7):
            dag_module._request_service("GET", "http://service.test")

        timeout = self.sent_requests[0].extensions["timeout"]
        self.assertEqual(timeout["read"], 7)
        self.assertEqual(timeout["connect"], 7)

    def test_explicit_timeout_overrides_default(self):
        self.patch_transport(lambda _: httpx.Response(200, json={}))

        dag_module._request_service("GET", "http://service.test", timeout_seconds=123)

        self.assertEqual(self.sent_requests[0].extensions["timeout"]["read"], 123)

    def test_disables_transport_retries(self):
        transport_class = self.patch_transport(lambda _: httpx.Response(200, json={}))

        dag_module._request_service("GET", "http://service.test")

        transport_class.assert_called_once_with(retries=0)

    def test_error_status_raises_airflow_exception_with_details(self):
        for status_code in (400, 404, 500, 503):
            with self.subTest(status_code=status_code):
                self.patch_transport(
                    lambda _, code=status_code: httpx.Response(code, text="boom")
                )

                with self.assertRaises(AirflowException) as raised:
                    dag_module._request_service("POST", "http://service.test/run")

                message = str(raised.exception)
                self.assertIn("POST http://service.test/run", message)
                self.assertIn(f"status={status_code}", message)
                self.assertIn("body=boom", message)
                self.assertIsInstance(raised.exception.__cause__, httpx.HTTPStatusError)

    def test_connection_error_is_not_swallowed(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused", request=request)

        self.patch_transport(refuse)

        with self.assertRaises(httpx.ConnectError):
            dag_module._request_service("GET", "http://service.test")


class TestRunAggregator(RequestServiceMixin, unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            dag_module, "AGGREGATOR_BASE_URL", "http://agg.test"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_accepted_response(self):
        response = {"status": "ACCEPTED", "workflow_id": "wf-1"}
        request_service = self.patch_request_service(return_value=response)

        self.assertEqual(dag_module.run_aggregator(), response)
        request_service.assert_called_once_with("POST", "http://agg.test/aggregate")

    def test_status_check_ignores_case(self):
        self.patch_request_service(
            return_value={"status": "accepted", "workflow_id": "wf-1"}
        )

        self.assertEqual(dag_module.run_aggregator()["workflow_id"], "wf-1")

    def test_rejects_unexpected_status(self):
        for response in (
            {"status": "REJECTED", "workflow_id": "wf-1"},
            {"status": None, "workflow_id": "wf-1"},
            {"workflow_id": "wf-1"},
            {"raw_response": "ACCEPTED"},
        ):
            with self.subTest(response=response):
                self.patch_request_service(return_value=response)

                with self.assertRaisesRegex(AirflowException, "unexpected status"):
                    dag_module.run_aggregator()

    def test_rejects_missing_workflow_id(self):
        for response in (
            {"status": "ACCEPTED"},
            {"status": "ACCEPTED", "workflow_id": ""},
            {"status": "ACCEPTED", "workflow_id": None},
        ):
            with self.subTest(response=response):
                self.patch_request_service(return_value=response)

                with self.assertRaisesRegex(AirflowException, "missing workflow_id"):
                    dag_module.run_aggregator()


class TestRunStats(RequestServiceMixin, unittest.TestCase):
    def setUp(self):
        for name, value in (
            ("STATS_BASE_URL", "http://stats.test"),
            ("STATS_REQUEST_TIMEOUT_SECONDS", 321),
        ):
            patcher = mock.patch.object(dag_module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_accepts_completed_and_skipped_in_any_case(self):
        for status in ("completed", "COMPLETED", "skipped", "Skipped"):
            with self.subTest(status=status):
                response = {"status": status}
                self.patch_request_service(return_value=response)

                self.assertEqual(dag_module.run_stats(), response)

    def test_uses_stats_url_and_longer_timeout(self):
        request_service = self.patch_request_service(
            return_value={"status": "completed"}
        )

        dag_module.run_stats()

        request_service.assert_called_once_with(
            "POST", "http://stats.test/stats", timeout_seconds=321
        )

    def test_rejects_other_statuses(self):
        for response in (
            {"status": "failed"},
            {"status": None},
            {},
            {"raw_response": ""},
        ):
            with self.subTest(response=response):
                self.patch_request_service(return_value=response)

                with self.assertRaisesRegex(AirflowException, "unexpected status"):
                    dag_module.run_stats()


class TestWaitForWorkflowCompletion(RequestServiceMixin, unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            dag_module, "AGGREGATOR_BASE_URL", "http://agg.test"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reads_workflow_id_from_aggregator_task(self):
        self.patch_request_service(return_value={"status": "STARTED"})
        context = make_context({"workflow_id": "wf-9"})

        dag_module.wait_for_workflow_completion(**context)

        context["ti"].xcom_pull.assert_called_once_with(task_ids="run_aggregator")

    def test_polls_workflow_status_url(self):
        request_service = self.patch_request_service(return_value={"status": "STARTED"})

        dag_module.wait_for_workflow_completion(**make_context({"workflow_id": "wf-9"}))

        request_service.assert_called_once_with("GET", "http://agg.test/aggregate/wf-9")

    def test_started_keeps_sensor_waiting(self):
        self.patch_request_service(return_value={"status": "STARTED"})
        context = make_context({"workflow_id": "wf-1"})

        self.assertFalse(dag_module.wait_for_workflow_completion(**context))
        context["ti"].xcom_push.assert_not_called()

    def test_final_status_finishes_sensor_and_is_pushed(self):
        for status in ("COMPLETED", "FAILED"):
            with self.subTest(status=status):
                self.patch_request_service(return_value={"status": status})
                context = make_context({"workflow_id": "wf-1"})

                self.assertTrue(dag_module.wait_for_workflow_completion(**context))
                context["ti"].xcom_push.assert_called_once_with(
                    key="final_workflow_status", value=status
                )

    def test_unknown_status_raises(self):
        # Unlike the other tasks, this status check is case-sensitive.
        for response in ({"status": "completed"}, {"status": "QUEUED"}, {}):
            with self.subTest(response=response):
                self.patch_request_service(return_value=response)

                with self.assertRaisesRegex(
                    AirflowException, "Unexpected workflow status"
                ):
                    dag_module.wait_for_workflow_completion(
                        **make_context({"workflow_id": "wf-1"})
                    )

    def test_missing_workflow_id_raises_without_request(self):
        for xcom_value in (None, {}, {"workflow_id": ""}, {"status": "ACCEPTED"}):
            with self.subTest(xcom_value=xcom_value):
                request_service = self.patch_request_service()

                with self.assertRaisesRegex(AirflowException, "No workflow_id"):
                    dag_module.wait_for_workflow_completion(**make_context(xcom_value))
                request_service.assert_not_called()


class TestChooseHousekeepingBranch(unittest.TestCase):
    ANCHOR = date(2026, 1, 1)

    def setUp(self):
        for name, value in (
            ("HOUSEKEEPING_ANCHOR_DATE", self.ANCHOR),
            ("HOUSEKEEPING_EVERY_N_DAYS", 5),
        ):
            patcher = mock.patch.object(dag_module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def choose(self, final_status="COMPLETED", logical_date=None) -> str:
        context = make_context(final_status, logical_date)
        return dag_module.choose_housekeeping_branch(**context)

    def test_reads_final_status_from_sensor(self):
        context = make_context("COMPLETED")

        dag_module.choose_housekeeping_branch(**context)

        context["ti"].xcom_pull.assert_called_once_with(
            task_ids="wait_for_aggregator_workflow", key="final_workflow_status"
        )

    def test_skips_when_workflow_did_not_complete(self):
        housekeeping_day = datetime(2026, 1, 6, 12, 0, tzinfo=UTC)
        for final_status in ("FAILED", None, "completed"):
            with self.subTest(final_status=final_status):
                self.assertEqual(
                    self.choose(final_status, housekeeping_day), "skip_housekeeping"
                )

    def test_runs_every_n_days_from_anchor(self):
        expected = {
            date(2026, 1, 1): "run_housekeeping",
            date(2026, 1, 2): "skip_housekeeping",
            date(2026, 1, 5): "skip_housekeeping",
            date(2026, 1, 6): "run_housekeeping",
            date(2026, 1, 7): "skip_housekeeping",
            date(2026, 1, 11): "run_housekeeping",
            date(2026, 3, 2): "run_housekeeping",
        }
        for day, branch in expected.items():
            with self.subTest(day=day):
                logical_date = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
                self.assertEqual(self.choose(logical_date=logical_date), branch)

    def test_skips_before_anchor_even_on_multiple_of_n(self):
        # Five days before the anchor gives -5 % 5 == 0, so only the `>= 0` check skips it.
        logical_date = datetime(2025, 12, 27, 12, tzinfo=UTC)

        self.assertEqual(self.choose(logical_date=logical_date), "skip_housekeeping")

    def test_every_day_when_n_is_one(self):
        with mock.patch.object(dag_module, "HOUSEKEEPING_EVERY_N_DAYS", 1):
            for day in range(1, 8):
                with self.subTest(day=day):
                    logical_date = datetime(2026, 1, day, 12, tzinfo=UTC)
                    self.assertEqual(
                        self.choose(logical_date=logical_date), "run_housekeeping"
                    )

    def test_returned_branch_names_exist_in_dag(self):
        task_ids = set(dag_module.dag.task_dict)
        for final_status in ("COMPLETED", "FAILED"):
            with self.subTest(final_status=final_status):
                self.assertIn(self.choose(final_status), task_ids)

    @unittest.expectedFailure
    def test_uses_local_date_of_run(self):
        """Documents an open question: which calendar day the 00:05 run counts as.

        Airflow passes `logical_date` in UTC. The run scheduled for 2026-01-06 00:05 in
        Europe/Paris has the logical date 2026-01-05 23:05 UTC, so the branch counts
        4 days since the anchor instead of 5 and skips housekeeping.

        The cadence is still every N days, only shifted by one day. Remove the decorator
        if the branch is changed to use the local date, or delete this test if the shift
        is intended.
        """
        run_at_local_midnight = datetime(2026, 1, 5, 23, 5, tzinfo=UTC)

        self.assertEqual(
            self.choose(logical_date=run_at_local_midnight), "run_housekeeping"
        )


class TestRunHousekeeping(RequestServiceMixin, unittest.TestCase):
    def test_calls_delete_endpoint(self):
        request_service = self.patch_request_service(return_value={"deleted": 3})

        with mock.patch.object(dag_module, "HOUSEKEEPING_BASE_URL", "http://hk.test"):
            result = dag_module.run_housekeeping()

        self.assertEqual(result, {"deleted": 3})
        request_service.assert_called_once_with("DELETE", "http://hk.test/delete")

    def test_propagates_request_error(self):
        self.patch_request_service(side_effect=AirflowException("status=500"))

        with self.assertRaises(AirflowException):
            dag_module.run_housekeeping()


class TestTriggerDbBackup(RequestServiceMixin, unittest.TestCase):
    def setUp(self):
        for name, value in (
            ("DB_BACKUP_BASE_URL", "http://backup.test:8080"),
            ("DB_BACKUP_WORKFLOW_NAME", "backup_wf"),
            ("DB_BACKUP_WORKFLOW_VERSION", "3"),
        ):
            patcher = mock.patch.object(dag_module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_starts_named_workflow_version(self):
        request_service = self.patch_request_service(return_value={"workflowId": "id"})

        dag_module.trigger_db_backup()

        request_service.assert_called_once_with(
            "POST",
            "http://backup.test:8080/api/workflow/backup_wf?version=3",
            json_payload={},
        )

    def test_reads_workflow_id_from_any_supported_field(self):
        cases = {
            "camel case key": ({"workflowId": "a-1"}, "a-1"),
            "snake case key": ({"workflow_id": "b-2"}, "b-2"),
            "plain text body": ({"raw_response": "c-3"}, "c-3"),
            "plain text with whitespace": ({"raw_response": "  d-4\n"}, "d-4"),
            "camel case wins": ({"workflowId": "e-5", "raw_response": "x"}, "e-5"),
            "falls through empty key": (
                {"workflowId": "", "workflow_id": "f-6"},
                "f-6",
            ),
            "non-string id": ({"workflowId": 42}, "42"),
        }
        for name, (response, expected_id) in cases.items():
            with self.subTest(name):
                self.patch_request_service(return_value=response)

                self.assertEqual(
                    dag_module.trigger_db_backup(), {"workflow_id": expected_id}
                )

    def test_plain_string_response_is_accepted(self):
        self.patch_request_service(return_value=" g-7 ")

        self.assertEqual(dag_module.trigger_db_backup(), {"workflow_id": "g-7"})

    def test_missing_workflow_id_raises(self):
        for response in ({}, {"raw_response": ""}, {"raw_response": "   \n"}, None):
            with self.subTest(response=response):
                self.patch_request_service(return_value=response)

                with self.assertRaisesRegex(AirflowException, "missing workflow id"):
                    dag_module.trigger_db_backup()


class TestWaitForDbBackupCompletion(RequestServiceMixin, unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            dag_module, "DB_BACKUP_BASE_URL", "http://backup.test:8080"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def poke(self, response, workflow_id="wf-1") -> bool:
        self.patch_request_service(return_value=response)
        return dag_module.wait_for_db_backup_completion(
            **make_context({"workflow_id": workflow_id})
        )

    def test_polls_workflow_url_from_trigger_task(self):
        request_service = self.patch_request_service(
            return_value={"status": "COMPLETED"}
        )
        context = make_context({"workflow_id": "wf-77"})

        dag_module.wait_for_db_backup_completion(**context)

        context["ti"].xcom_pull.assert_called_once_with(task_ids="trigger_db_backup")
        request_service.assert_called_once_with(
            "GET", "http://backup.test:8080/api/workflow/wf-77"
        )

    def test_completed_finishes_sensor(self):
        for status in ("COMPLETED", "completed"):
            with self.subTest(status=status):
                self.assertTrue(self.poke({"status": status}))

    def test_running_statuses_keep_sensor_waiting(self):
        for status in ("RUNNING", "IN_PROGRESS", "PAUSED", "running"):
            with self.subTest(status=status):
                self.assertFalse(self.poke({"status": status}))

    def test_failed_statuses_raise(self):
        for status in ("FAILED", "TERMINATED", "TIMED_OUT", "failed"):
            with self.subTest(status=status):
                with self.assertRaisesRegex(AirflowException, f"status: {status}"):
                    self.poke({"status": status})

    def test_missing_status_raises(self):
        for response in ({}, {"status": None}, {"status": ""}, "COMPLETED"):
            with self.subTest(response=response):
                with self.assertRaisesRegex(AirflowException, "<missing>"):
                    self.poke(response)

    def test_unknown_status_raises(self):
        with self.assertRaisesRegex(AirflowException, "SCHEDULED"):
            self.poke({"status": "SCHEDULED"})

    def test_missing_workflow_id_raises_without_request(self):
        for xcom_value in (None, {}, {"workflow_id": ""}):
            with self.subTest(xcom_value=xcom_value):
                request_service = self.patch_request_service()

                with self.assertRaisesRegex(AirflowException, "No workflow_id"):
                    dag_module.wait_for_db_backup_completion(**make_context(xcom_value))
                request_service.assert_not_called()


class TestSettingsFromEnvironment(unittest.TestCase):
    """Loads a separate copy of the DAG file, so the shared module keeps its settings."""

    SETTING_NAMES = (
        "AGGREGATOR_BASE_URL",
        "DB_BACKUP_HOST",
        "DB_BACKUP_PORT",
        "DB_BACKUP_POLL_INTERVAL_SECONDS",
        "HOUSEKEEPING_ANCHOR_DATE",
        "HOUSEKEEPING_EVERY_N_DAYS",
        "TIMEZONE",
        "WORKFLOW_POLL_INTERVAL_SECONDS",
    )

    def load_with_env(self, **values):
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in self.SETTING_NAMES
        }
        environment.update(values)
        with mock.patch.dict(os.environ, environment, clear=True):
            return load_fresh_dag_module("pnls_orchestrator_dag_settings_test")

    def test_defaults(self):
        module = self.load_with_env()

        self.assertEqual(module.AGGREGATOR_BASE_URL, "http://aggregator:9091")
        self.assertEqual(module.DB_BACKUP_BASE_URL, "http://localhost:8080")
        self.assertEqual(module.HOUSEKEEPING_EVERY_N_DAYS, 5)
        self.assertEqual(module.HOUSEKEEPING_ANCHOR_DATE, date(2026, 1, 1))
        self.assertEqual(module.TIMEZONE, "Europe/Paris")

    def test_values_are_read_and_converted(self):
        module = self.load_with_env(
            AGGREGATOR_BASE_URL="http://agg:1",
            DB_BACKUP_HOST="backup-host",
            DB_BACKUP_PORT="9999",
            HOUSEKEEPING_ANCHOR_DATE="2025-06-01",
            HOUSEKEEPING_EVERY_N_DAYS="3",
            WORKFLOW_POLL_INTERVAL_SECONDS="17",
            DB_BACKUP_POLL_INTERVAL_SECONDS="11",
        )

        self.assertEqual(module.AGGREGATOR_BASE_URL, "http://agg:1")
        self.assertEqual(module.DB_BACKUP_BASE_URL, "http://backup-host:9999")
        self.assertEqual(module.HOUSEKEEPING_ANCHOR_DATE, date(2025, 6, 1))
        self.assertEqual(module.HOUSEKEEPING_EVERY_N_DAYS, 3)
        self.assertEqual(
            module.dag.get_task("wait_for_aggregator_workflow").poke_interval, 17
        )
        self.assertEqual(
            module.dag.get_task("wait_for_db_backup_workflow").poke_interval, 11
        )

    def test_dag_start_date_uses_configured_timezone(self):
        # Midnight on 2026-01-01 in Tokyo (UTC+9) is 15:00 UTC on the day before.
        module = self.load_with_env(TIMEZONE="Asia/Tokyo")

        self.assertEqual(
            module.dag.start_date, datetime(2025, 12, 31, 15, 0, tzinfo=UTC)
        )

    def test_invalid_values_fail_the_dag_import(self):
        for name, value in (
            ("HOUSEKEEPING_EVERY_N_DAYS", "five"),
            ("WORKFLOW_POLL_INTERVAL_SECONDS", ""),
            ("HOUSEKEEPING_ANCHOR_DATE", "01.01.2026"),
        ):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.load_with_env(**{name: value})


if __name__ == "__main__":
    unittest.main()
