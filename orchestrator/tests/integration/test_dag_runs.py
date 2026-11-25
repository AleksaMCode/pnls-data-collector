"""Runs the whole orchestrator DAG with `dag.test()` against faked services."""

import unittest
from datetime import UTC, datetime
from unittest import mock
from urllib.parse import urlsplit

from orchestrator.tests.dag_loader import load_dag_module

dag_module = load_dag_module()
dag = dag_module.dag

# 2026-01-01 is the default housekeeping anchor and housekeeping runs every 5 days.
# Midday UTC keeps the logical date on the same calendar day in every timezone near Europe.
HOUSEKEEPING_DAYS = iter(
    datetime(2026, 1, day, 12, tzinfo=UTC) for day in (6, 11, 16, 21)
)
OTHER_DAYS = iter(datetime(2026, 2, day, 12, tzinfo=UTC) for day in range(1, 29))

AGGREGATE = ("POST", "/aggregate")
AGGREGATE_STATUS = ("GET", "/aggregate/agg-wf-1")
STATS = ("POST", "/stats")
HOUSEKEEPING = ("DELETE", "/delete")
BACKUP_TRIGGER = ("POST", f"/api/workflow/{dag_module.DB_BACKUP_WORKFLOW_NAME}")
BACKUP_STATUS = ("GET", "/api/workflow/backup-wf-1")


class FakeServices:
    """Stands in for `_request_service` and records each call as (method, path)."""

    def __init__(self, **overrides):
        self.responses = {
            AGGREGATE: {"status": "ACCEPTED", "workflow_id": "agg-wf-1"},
            AGGREGATE_STATUS: {"status": "COMPLETED"},
            STATS: {"status": "completed"},
            HOUSEKEEPING: {"deleted": 0},
            BACKUP_TRIGGER: {"raw_response": "backup-wf-1"},
            BACKUP_STATUS: {"status": "COMPLETED"},
        }
        self.responses.update(overrides)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, url, json_payload=None, timeout_seconds=None):
        route = (method, urlsplit(url).path)
        self.calls.append(route)
        if route not in self.responses:
            raise AssertionError(f"Unexpected request {method} {url}")

        response = self.responses[route]
        if isinstance(response, Exception):
            raise response
        return response


def task_states(dag_run) -> dict[str, str | None]:
    from airflow.models.taskinstance import TaskInstance
    from airflow.utils.session import create_session
    from sqlalchemy import select

    with create_session() as session:
        rows = session.execute(
            select(TaskInstance.task_id, TaskInstance.state).where(
                TaskInstance.dag_id == dag.dag_id,
                TaskInstance.run_id == dag_run.run_id,
            )
        ).all()
    return {task_id: _state_name(state) for task_id, state in rows}


def _state_name(state) -> str | None:
    return None if state is None else str(getattr(state, "value", state))


class TestDagRuns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from airflow.utils import db

        db.initdb()

        # A failed task would otherwise wait 5 minutes for its retry.
        cls.original_retries = {task.task_id: task.retries for task in dag.tasks}
        for task in dag.tasks:
            task.retries = 0

    @classmethod
    def tearDownClass(cls):
        for task in dag.tasks:
            task.retries = cls.original_retries[task.task_id]

    def run_dag(self, logical_date: datetime, services: FakeServices):
        with mock.patch.object(dag_module, "_request_service", side_effect=services):
            dag_run = dag.test(logical_date=logical_date)
        return dag_run, task_states(dag_run)

    def test_housekeeping_day_runs_every_service(self):
        services = FakeServices()

        dag_run, states = self.run_dag(next(HOUSEKEEPING_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "success")
        self.assertEqual(
            states,
            {
                "run_aggregator": "success",
                "wait_for_aggregator_workflow": "success",
                "run_stats": "success",
                "branch_housekeeping": "success",
                "run_housekeeping": "success",
                "skip_housekeeping": "skipped",
                "done": "success",
                "trigger_db_backup": "success",
                "wait_for_db_backup_workflow": "success",
            },
        )
        self.assertEqual(
            services.calls,
            [
                AGGREGATE,
                AGGREGATE_STATUS,
                STATS,
                HOUSEKEEPING,
                BACKUP_TRIGGER,
                BACKUP_STATUS,
            ],
        )

    def test_other_days_skip_housekeeping_but_still_back_up(self):
        services = FakeServices()

        dag_run, states = self.run_dag(next(OTHER_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "success")
        self.assertEqual(states["run_housekeeping"], "skipped")
        self.assertEqual(states["skip_housekeeping"], "success")
        self.assertEqual(states["done"], "success")
        self.assertEqual(states["wait_for_db_backup_workflow"], "success")
        self.assertNotIn(HOUSEKEEPING, services.calls)
        self.assertIn(BACKUP_STATUS, services.calls)

    def test_workflow_id_is_passed_between_tasks(self):
        services = FakeServices(
            **{
                AGGREGATE: {"status": "ACCEPTED", "workflow_id": "agg-wf-2"},
                ("GET", "/aggregate/agg-wf-2"): {"status": "COMPLETED"},
                BACKUP_TRIGGER: {"workflowId": "backup-wf-2"},
                ("GET", "/api/workflow/backup-wf-2"): {"status": "COMPLETED"},
            }
        )

        dag_run, _ = self.run_dag(next(OTHER_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "success")
        self.assertIn(("GET", "/aggregate/agg-wf-2"), services.calls)
        self.assertIn(("GET", "/api/workflow/backup-wf-2"), services.calls)

    def test_failed_aggregation_still_runs_stats_and_backup(self):
        # Current behaviour: a FAILED aggregation workflow finishes the sensor successfully,
        # so stats still run and only housekeeping is skipped, even on a housekeeping day.
        # Change this test if stats should not run after a failed aggregation.
        services = FakeServices(**{AGGREGATE_STATUS: {"status": "FAILED"}})

        dag_run, states = self.run_dag(next(HOUSEKEEPING_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "success")
        self.assertEqual(states["wait_for_aggregator_workflow"], "success")
        self.assertEqual(states["run_stats"], "success")
        self.assertEqual(states["run_housekeeping"], "skipped")
        self.assertEqual(states["skip_housekeeping"], "success")
        self.assertEqual(states["wait_for_db_backup_workflow"], "success")
        self.assertNotIn(HOUSEKEEPING, services.calls)

    def test_failed_aggregator_trigger_stops_the_run(self):
        services = FakeServices(
            **{AGGREGATE: dag_module.AirflowException("status=503 body=down")}
        )

        dag_run, states = self.run_dag(next(OTHER_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "failed")
        self.assertEqual(states["run_aggregator"], "failed")
        for task_id in ("wait_for_aggregator_workflow", "run_stats", "done"):
            with self.subTest(task_id=task_id):
                self.assertEqual(states[task_id], "upstream_failed")
        self.assertEqual(services.calls, [AGGREGATE])

    def test_failed_stats_stop_housekeeping_and_backup(self):
        services = FakeServices(**{STATS: {"status": "failed"}})

        dag_run, states = self.run_dag(next(HOUSEKEEPING_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "failed")
        self.assertEqual(states["run_stats"], "failed")
        self.assertEqual(states["branch_housekeeping"], "upstream_failed")
        self.assertEqual(states["trigger_db_backup"], "upstream_failed")
        self.assertNotIn(HOUSEKEEPING, services.calls)
        self.assertNotIn(BACKUP_TRIGGER, services.calls)

    def test_failed_housekeeping_skips_the_backup(self):
        # Current behaviour: `done` needs no failed upstream task, so a failed housekeeping
        # call also stops the DB backup. Change this test if the backup should still run.
        services = FakeServices(
            **{HOUSEKEEPING: dag_module.AirflowException("status=500 body=boom")}
        )

        dag_run, states = self.run_dag(next(HOUSEKEEPING_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "failed")
        self.assertEqual(states["run_housekeeping"], "failed")
        self.assertEqual(states["skip_housekeeping"], "skipped")
        self.assertEqual(states["done"], "upstream_failed")
        self.assertEqual(states["trigger_db_backup"], "upstream_failed")
        self.assertEqual(states["wait_for_db_backup_workflow"], "upstream_failed")
        self.assertNotIn(BACKUP_TRIGGER, services.calls)

    def test_failed_backup_workflow_fails_the_run(self):
        services = FakeServices(**{BACKUP_STATUS: {"status": "TERMINATED"}})

        dag_run, states = self.run_dag(next(OTHER_DAYS), services)

        self.assertEqual(_state_name(dag_run.state), "failed")
        self.assertEqual(states["trigger_db_backup"], "success")
        self.assertEqual(states["wait_for_db_backup_workflow"], "failed")


if __name__ == "__main__":
    unittest.main()
