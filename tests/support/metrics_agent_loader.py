"""Imports collector_metrics_agent modules without pointing the Datadog client at the real account."""

import importlib
from unittest import mock


def import_metrics_agent_module(name: str):
    """Imports a metrics agent module, e.g. `collector_metrics_agent.main`.

    `collector_metrics_agent.datadog` calls `datadog.initialize()` on import with the API key from
    the local `.env`, unless `ENV=test`. It is replaced here, so no test can send metrics to the
    real account: unit tests replace `api`, and integration tests point it at a local fake server.
    """
    with mock.patch("datadog.initialize"):
        return importlib.import_module(name)
