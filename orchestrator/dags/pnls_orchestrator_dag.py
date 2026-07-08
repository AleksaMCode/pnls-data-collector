import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import (
    BranchPythonOperator,
    PythonOperator,
)
from airflow.providers.standard.sensors.python import PythonSensor
from airflow.sdk import TriggerRule

logger = logging.getLogger(__name__)

AGGREGATOR_BASE_URL = os.getenv("AGGREGATOR_BASE_URL", "http://aggregator:9091")
HOUSEKEEPING_BASE_URL = os.getenv(
    "HOUSEKEEPING_BASE_URL", "http://firebase_housekeeping:9090"
)
DB_BACKUP_HOST = os.getenv("DB_BACKUP_HOST", "localhost")
DB_BACKUP_PORT = os.getenv("DB_BACKUP_PORT", "8080")
DB_BACKUP_WORKFLOW_NAME = os.getenv("DB_BACKUP_WORKFLOW_NAME", "db_backup_workflow")
DB_BACKUP_WORKFLOW_VERSION = os.getenv("DB_BACKUP_WORKFLOW_VERSION", "1")
DB_BACKUP_POLL_INTERVAL_SECONDS = int(
    os.getenv("DB_BACKUP_POLL_INTERVAL_SECONDS", "60")
)
DB_BACKUP_POLL_TIMEOUT_SECONDS = int(
    os.getenv("DB_BACKUP_POLL_TIMEOUT_SECONDS", "86400")
)
DB_BACKUP_BASE_URL = f"http://{DB_BACKUP_HOST}:{DB_BACKUP_PORT}"
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris")
HOUSEKEEPING_EVERY_N_DAYS = int(os.getenv("HOUSEKEEPING_EVERY_N_DAYS", "5"))
WORKFLOW_POLL_INTERVAL_SECONDS = int(os.getenv("WORKFLOW_POLL_INTERVAL_SECONDS", "300"))
WORKFLOW_POLL_TIMEOUT_SECONDS = int(os.getenv("WORKFLOW_POLL_TIMEOUT_SECONDS", "86400"))
HOUSEKEEPING_ANCHOR_DATE = date.fromisoformat(
    os.getenv("HOUSEKEEPING_ANCHOR_DATE", "2026-01-01")
)


def _request_service(method: str, url: str, json_payload: dict | None = None) -> dict:
    transport = httpx.HTTPTransport(retries=0)

    with httpx.Client(transport=transport) as client:
        response = client.request(
            method, url, timeout=REQUEST_TIMEOUT_SECONDS, json=json_payload
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            raise AirflowException(
                f"Request failed {method} {url} status={response.status_code} body={response.text}"
            ) from err

        if "application/json" in response.headers.get("content-type", ""):
            return response.json()

        return {"raw_response": response.text}


def run_aggregator() -> dict:
    response = _request_service("POST", f"{AGGREGATOR_BASE_URL}/aggregate")
    if (response.get("status") or "").upper() != "ACCEPTED":
        raise AirflowException(
            f"Aggregator returned unexpected status: {response.get('status')}"
        )
    if not response.get("workflow_id"):
        raise AirflowException("Aggregator response missing workflow_id.")
    return response


def wait_for_workflow_completion(**context) -> bool:
    trigger_response = context["ti"].xcom_pull(task_ids="run_aggregator") or {}
    workflow_id = trigger_response.get("workflow_id", None)
    if not workflow_id:
        raise AirflowException("No workflow_id found in aggregator response.")

    response = _request_service("GET", f"{AGGREGATOR_BASE_URL}/aggregate/{workflow_id}")
    status = response.get("status")
    if status not in {"STARTED", "COMPLETED", "FAILED"}:
        raise AirflowException(f"Unexpected workflow status: {status}")

    if status in {"COMPLETED", "FAILED"}:
        context["ti"].xcom_push(key="final_workflow_status", value=status)
        return True

    return False


def choose_housekeeping_branch(**context) -> str:
    final_workflow_status = context["ti"].xcom_pull(
        task_ids="wait_for_aggregator_workflow", key="final_workflow_status"
    )
    if final_workflow_status != "COMPLETED":
        return "skip_housekeeping"

    logical_date = context["logical_date"].date()
    days_since_anchor = (logical_date - HOUSEKEEPING_ANCHOR_DATE).days

    logger.info(
        "Branch decision inputs: final_workflow_status=%s logical_date=%s anchor=%s every_n_days=%s days_since_anchor=%s",
        final_workflow_status,
        logical_date,
        HOUSEKEEPING_ANCHOR_DATE,
        HOUSEKEEPING_EVERY_N_DAYS,
        days_since_anchor,
    )

    should_run_housekeeping = (
        days_since_anchor >= 0 and days_since_anchor % HOUSEKEEPING_EVERY_N_DAYS == 0
    )

    return "run_housekeeping" if should_run_housekeeping else "skip_housekeeping"


def run_housekeeping() -> dict:
    return _request_service("DELETE", f"{HOUSEKEEPING_BASE_URL}/delete")


def trigger_db_backup() -> dict:
    response = _request_service(
        "POST",
        f"{DB_BACKUP_BASE_URL}/api/workflow/{DB_BACKUP_WORKFLOW_NAME}?version={DB_BACKUP_WORKFLOW_VERSION}",
        json_payload={},
    )

    workflow_id = None
    if isinstance(response, dict):
        workflow_id = (
            response.get("workflowId")
            or response.get("workflow_id")
            or response.get("raw_response")
        )
    elif isinstance(response, str):
        workflow_id = response

    if isinstance(workflow_id, str):
        workflow_id = workflow_id.strip()

    if not workflow_id:
        raise AirflowException(
            f"DB backup trigger response missing workflow id. response={response}"
        )

    return {"workflow_id": str(workflow_id)}


def wait_for_db_backup_completion(**context) -> bool:
    trigger_response = context["ti"].xcom_pull(task_ids="trigger_db_backup") or {}
    workflow_id = trigger_response.get("workflow_id")
    if not workflow_id:
        raise AirflowException("No workflow_id found in db backup trigger response.")

    response = _request_service(
        "GET", f"{DB_BACKUP_BASE_URL}/api/workflow/{workflow_id}"
    )
    status = (response.get("status") if isinstance(response, dict) else None) or ""
    normalized_status = status.upper()

    if normalized_status == "COMPLETED":
        return True
    if normalized_status in {"FAILED", "TERMINATED", "TIMED_OUT"}:
        raise AirflowException(f"DB backup workflow failed with status: {status}")
    if normalized_status in {"RUNNING", "IN_PROGRESS", "PAUSED"}:
        return False

    raise AirflowException(
        f"Unexpected db backup workflow status: {status or '<missing>'}"
    )


with DAG(
    dag_id="pnls_orchestrator",
    description="Run aggregator daily, poll workflow status, and run housekeeping every N days.",
    start_date=datetime(2026, 1, 1, tzinfo=ZoneInfo(TIMEZONE)),
    schedule="5 0 * * *",
    # No catchup means don't backfill missed runs since start_date.
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["pnls", "orchestration"],
) as dag:
    run_aggregator_task = PythonOperator(
        task_id="run_aggregator",
        python_callable=run_aggregator,
    )

    wait_for_aggregator_workflow_task = PythonSensor(
        task_id="wait_for_aggregator_workflow",
        python_callable=wait_for_workflow_completion,
        poke_interval=WORKFLOW_POLL_INTERVAL_SECONDS,
        timeout=WORKFLOW_POLL_TIMEOUT_SECONDS,
        mode="reschedule",
    )

    branching_task = BranchPythonOperator(
        task_id="branch_housekeeping",
        python_callable=choose_housekeeping_branch,
    )

    run_housekeeping_task = PythonOperator(
        task_id="run_housekeeping",
        python_callable=run_housekeeping,
    )

    skip_housekeeping_task = EmptyOperator(task_id="skip_housekeeping")

    done_task = EmptyOperator(
        task_id="done",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    trigger_db_backup_task = PythonOperator(
        task_id="trigger_db_backup",
        python_callable=trigger_db_backup,
    )

    wait_for_db_backup_task = PythonSensor(
        task_id="wait_for_db_backup_workflow",
        python_callable=wait_for_db_backup_completion,
        poke_interval=DB_BACKUP_POLL_INTERVAL_SECONDS,
        timeout=DB_BACKUP_POLL_TIMEOUT_SECONDS,
        mode="reschedule",
    )

    run_aggregator_task >> wait_for_aggregator_workflow_task >> branching_task
    branching_task >> run_housekeeping_task >> done_task
    branching_task >> skip_housekeeping_task >> done_task
    done_task >> trigger_db_backup_task >> wait_for_db_backup_task
