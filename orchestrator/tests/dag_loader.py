"""Imports the DAG file the same way the Airflow DAG processor does."""

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

DAGS_FOLDER = Path(__file__).resolve().parent.parent / "dags"
DAG_MODULE_NAME = "pnls_orchestrator_dag"
DAG_FILE = DAGS_FOLDER / f"{DAG_MODULE_NAME}.py"


def load_dag_module() -> ModuleType:
    """Returns the DAG module, shared by all tests.

    Airflow puts the DAGs folder on `sys.path` and imports each file as a top-level module,
    so the tests do the same.
    """
    if str(DAGS_FOLDER) not in sys.path:
        sys.path.insert(0, str(DAGS_FOLDER))
    return importlib.import_module(DAG_MODULE_NAME)


def load_fresh_dag_module(module_name: str) -> ModuleType:
    """Executes the DAG file again as a separate module.

    Used to check how the module-level settings are read from the environment, without
    changing the shared module that the other tests use.
    """
    spec = importlib.util.spec_from_file_location(module_name, DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
