"""Unit tests for the SQLAlchemy session listeners in aggregator/core/orm/event.py."""

import importlib
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import mock

import tests.support.aggregator_loader  # noqa: F401  Sets the DB_* variables the module needs.

event = importlib.import_module("aggregator.core.orm.event")
models = importlib.import_module("aggregator.core.orm.models")

FIXED_NOW = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)


def session(new=(), dirty=()):
    return SimpleNamespace(new=set(new), dirty=set(dirty))


class TestMacOuiResolver(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(event, "resolve_oui")
        self.resolve_oui = patcher.start()
        self.addCleanup(patcher.stop)

    def test_resolves_new_and_changed_macs_without_oui(self):
        new_mac = models.MAC(mac="00:11:22:33:44:55")
        changed_mac = models.MAC(mac="00:66:77:88:99:AA")
        fake_session = session(new=[new_mac], dirty=[changed_mac])

        event.mac_oui_resolver(fake_session)

        self.assertCountEqual(
            self.resolve_oui.call_args_list,
            [mock.call(fake_session, new_mac), mock.call(fake_session, changed_mac)],
        )

    def test_skips_macs_that_already_have_an_oui_and_other_objects(self):
        resolved_mac = models.MAC(mac="00:11:22:33:44:55", oui=5)
        other = models.SSID(ssid="CERN")

        event.mac_oui_resolver(session(new=[resolved_mac, other]))

        self.resolve_oui.assert_not_called()


class TestWorkflowEndTimestamp(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(event, "workflow_now", return_value=FIXED_NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_end(self, *workflows, dirty=False):
        fake_session = session(**{"dirty" if dirty else "new": workflows})
        event.imports_workflow_end_timestamp_setter(fake_session, None, None)

    def test_finished_workflows_get_an_end_time(self):
        for status in (models.WorkflowStatus.COMPLETED, models.WorkflowStatus.FAILED):
            for dirty in (False, True):
                with self.subTest(status=status, dirty=dirty):
                    workflow = models.ImportsWorkflow(status=status)

                    self.set_end(workflow, dirty=dirty)

                    self.assertEqual(workflow.end, FIXED_NOW)

    def test_running_workflow_has_no_end_time(self):
        workflow = models.ImportsWorkflow(status=models.WorkflowStatus.STARTED)

        self.set_end(workflow)

        self.assertIsNone(workflow.end)

    def test_existing_end_time_is_kept(self):
        earlier = datetime(2026, 6, 1, tzinfo=UTC)
        workflow = models.ImportsWorkflow(
            status=models.WorkflowStatus.COMPLETED, end=earlier
        )

        self.set_end(workflow)

        self.assertEqual(workflow.end, earlier)


if __name__ == "__main__":
    unittest.main()
