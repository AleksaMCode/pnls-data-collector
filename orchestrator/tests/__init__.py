"""Tests for the Airflow orchestrator DAG."""

import os
import tempfile
from pathlib import Path

_AIRFLOW_HOME = Path(tempfile.mkdtemp(prefix="pnls-airflow-tests-"))

os.environ["AIRFLOW_HOME"] = str(_AIRFLOW_HOME)
os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = (
    f"sqlite:///{(_AIRFLOW_HOME / 'airflow.db').as_posix()}"
)
os.environ["AIRFLOW__CORE__DAGS_FOLDER"] = str(Path(__file__).parent.parent / "dags")
os.environ["AIRFLOW__CORE__LOAD_EXAMPLES"] = "False"
os.environ["AIRFLOW__CORE__EXECUTOR"] = "LocalExecutor"
os.environ["AIRFLOW__SENTRY__SENTRY_ON"] = "False"
os.environ["AIRFLOW__LOGGING__LOGGING_LEVEL"] = "WARNING"
