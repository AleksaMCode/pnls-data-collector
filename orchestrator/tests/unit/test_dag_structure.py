"""Checks that the orchestrator DAG imports cleanly and keeps its intended shape."""

import unittest
from datetime import datetime, timedelta

from orchestrator.tests.dag_loader import DAGS_FOLDER, load_dag_module

dag_module = load_dag_module()
dag = dag_module.dag
TriggerRule = dag_module.TriggerRule

EXPECTED_DOWNSTREAM = {
    "run_aggregator": {"wait_for_aggregator_workflow"},
    "wait_for_aggregator_workflow": {"run_stats"},
    "run_stats": {"branch_housekeeping"},
    "branch_housekeeping": {"run_housekeeping", "skip_housekeeping"},
    "run_housekeeping": {"done"},
    "skip_housekeeping": {"done"},
    "done": {"trigger_db_backup"},
    "trigger_db_backup": {"wait_for_db_backup_workflow"},
    "wait_for_db_backup_workflow": set(),
}


def load_dag_bag():
    # DagBag moved out of `airflow.models` in Airflow 3.
    try:
        from airflow.dag_processing.dagbag import DagBag
    except ImportError:
        from airflow.models.dagbag import DagBag

    # Example DAGs are already off: the test package sets AIRFLOW__CORE__LOAD_EXAMPLES=False.
    return DagBag(dag_folder=str(DAGS_FOLDER))


class TestDagImport(unittest.TestCase):
    def test_dags_folder_has_no_import_errors(self):
        dag_bag = load_dag_bag()

        self.assertEqual(dag_bag.import_errors, {})
        self.assertEqual(set(dag_bag.dag_ids), {"pnls_orchestrator"})

    def test_dag_bag_contains_all_tasks(self):
        parsed_dag = load_dag_bag().get_dag("pnls_orchestrator")

        self.assertEqual(set(parsed_dag.task_dict), set(EXPECTED_DOWNSTREAM))


class TestDagSettings(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(dag.dag_id, "pnls_orchestrator")
        self.assertEqual(set(dag.tags), {"pnls", "orchestration"})
        self.assertTrue(dag.description)

    def test_schedule_runs_daily_at_five_past_midnight(self):
        self.assertEqual(dag.schedule, "5 0 * * *")

    def test_start_date_is_midnight_in_configured_timezone(self):
        expected = datetime(2026, 1, 1, tzinfo=dag_module.ZoneInfo(dag_module.TIMEZONE))

        self.assertEqual(dag.start_date, expected)

    def test_no_backfill_and_one_run_at_a_time(self):
        self.assertFalse(dag.catchup)
        self.assertEqual(dag.max_active_runs, 1)

    def test_every_task_retries_once_after_five_minutes(self):
        for task in dag.tasks:
            with self.subTest(task_id=task.task_id):
                self.assertEqual(task.retries, 1)
                self.assertEqual(task.retry_delay, timedelta(minutes=5))


class TestDagWiring(unittest.TestCase):
    def test_task_ids(self):
        self.assertEqual(set(dag.task_dict), set(EXPECTED_DOWNSTREAM))

    def test_dependencies(self):
        for task_id, downstream in EXPECTED_DOWNSTREAM.items():
            with self.subTest(task_id=task_id):
                self.assertEqual(dag.get_task(task_id).downstream_task_ids, downstream)

    def test_single_start_and_end(self):
        self.assertEqual([task.task_id for task in dag.roots], ["run_aggregator"])
        self.assertEqual(
            [task.task_id for task in dag.leaves], ["wait_for_db_backup_workflow"]
        )

    def test_done_joins_both_housekeeping_branches(self):
        self.assertEqual(
            dag.get_task("done").upstream_task_ids,
            {"run_housekeeping", "skip_housekeeping"},
        )

    def test_done_runs_after_the_skipped_branch(self):
        # With the default `all_success`, `done` would be skipped together with the
        # branch that was not chosen, and the DB backup would never run.
        self.assertEqual(
            dag.get_task("done").trigger_rule, TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
        )

    def test_other_tasks_need_all_upstream_tasks_to_succeed(self):
        for task in dag.tasks:
            if task.task_id == "done":
                continue
            with self.subTest(task_id=task.task_id):
                self.assertEqual(task.trigger_rule, TriggerRule.ALL_SUCCESS)


class TestTaskDefinitions(unittest.TestCase):
    def test_operator_types(self):
        expected = {
            "run_aggregator": dag_module.PythonOperator,
            "wait_for_aggregator_workflow": dag_module.PythonSensor,
            "run_stats": dag_module.PythonOperator,
            "branch_housekeeping": dag_module.BranchPythonOperator,
            "run_housekeeping": dag_module.PythonOperator,
            "skip_housekeeping": dag_module.EmptyOperator,
            "done": dag_module.EmptyOperator,
            "trigger_db_backup": dag_module.PythonOperator,
            "wait_for_db_backup_workflow": dag_module.PythonSensor,
        }
        for task_id, operator_class in expected.items():
            with self.subTest(task_id=task_id):
                self.assertIsInstance(dag.get_task(task_id), operator_class)

    def test_python_callables(self):
        expected = {
            "run_aggregator": dag_module.run_aggregator,
            "wait_for_aggregator_workflow": dag_module.wait_for_workflow_completion,
            "run_stats": dag_module.run_stats,
            "branch_housekeeping": dag_module.choose_housekeeping_branch,
            "run_housekeeping": dag_module.run_housekeeping,
            "trigger_db_backup": dag_module.trigger_db_backup,
            "wait_for_db_backup_workflow": dag_module.wait_for_db_backup_completion,
        }
        for task_id, callable_ in expected.items():
            with self.subTest(task_id=task_id):
                self.assertIs(dag.get_task(task_id).python_callable, callable_)

    def test_branch_targets_are_direct_downstream_tasks(self):
        # A BranchPythonOperator can only choose between its own downstream tasks.
        branch = dag.get_task("branch_housekeeping")

        self.assertLessEqual(
            {"run_housekeeping", "skip_housekeeping"}, branch.downstream_task_ids
        )

    def test_sensors_release_the_worker_while_waiting(self):
        for task_id in ("wait_for_aggregator_workflow", "wait_for_db_backup_workflow"):
            with self.subTest(task_id=task_id):
                self.assertEqual(dag.get_task(task_id).mode, "reschedule")

    def test_sensor_intervals_come_from_settings(self):
        expected = {
            "wait_for_aggregator_workflow": (
                dag_module.WORKFLOW_POLL_INTERVAL_SECONDS,
                dag_module.WORKFLOW_POLL_TIMEOUT_SECONDS,
            ),
            "wait_for_db_backup_workflow": (
                dag_module.DB_BACKUP_POLL_INTERVAL_SECONDS,
                dag_module.DB_BACKUP_POLL_TIMEOUT_SECONDS,
            ),
        }
        for task_id, (poke_interval, timeout) in expected.items():
            with self.subTest(task_id=task_id):
                sensor = dag.get_task(task_id)
                self.assertEqual(sensor.poke_interval, poke_interval)
                self.assertEqual(sensor.timeout, timeout)
