import unittest
import uuid
from datetime import date, datetime

from aggregator.core.orm.models import MAC, ImportsInfo, ImportsWorkflow, WorkflowStatus


class TestMACValidator(unittest.TestCase):

    def test_mac_sets_uaa_flag(self):
        cases = [
            # (mac, expected_uaa)
            ("00:00:00:00:00:00", True),  # universal
            ("02:00:00:00:00:00", False),  # locally administered
            ("AA:BB:CC:DD:EE:FF", False),
            ("AE:BB:CC:DD:EE:FF", False),
            ("06:11:22:33:44:55", False),
        ]
        for mac_value, expected in cases:
            with self.subTest(mac=mac_value):
                mac = MAC(mac=mac_value)
                self.assertEqual(mac.uaa, expected)


class TestImportsInfoDefaults(unittest.TestCase):

    def test_workflow_id_default_is_null(self):
        self.assertIsNone(ImportsInfo.__table__.c.workflow_id.default)

    def test_timestamp_default_is_today(self):
        default_callable = ImportsInfo.__table__.c.timestamp.default.arg

        self.assertEqual(default_callable(None), date.today())

    def test_captured_default_is_zero(self):
        self.assertEqual(ImportsInfo.__table__.c.captured.default.arg, 0)


class TestImportsWorkflowDefaults(unittest.TestCase):

    def test_id_default_generates_uuid4(self):
        default_callable = ImportsWorkflow.__table__.c.id.default.arg

        first_value = default_callable(None)
        second_value = default_callable(None)

        self.assertIsInstance(first_value, uuid.UUID)
        self.assertIsInstance(second_value, uuid.UUID)
        self.assertEqual(first_value.version, 4)
        self.assertEqual(second_value.version, 4)
        self.assertNotEqual(first_value, second_value)

    def test_status_enum_values(self):
        self.assertEqual(WorkflowStatus.STARTED.value, "STARTED")
        self.assertEqual(WorkflowStatus.COMPLETED.value, "COMPLETED")
        self.assertEqual(WorkflowStatus.FAILED.value, "FAILED")

    def test_status_default_is_started(self):
        self.assertEqual(
            ImportsWorkflow.__table__.c.status.default.arg,
            WorkflowStatus.STARTED,
        )

    def test_start_default_is_timezone_aware_datetime(self):
        default_callable = ImportsWorkflow.__table__.c.start.default.arg
        value = default_callable(None)

        self.assertIsInstance(value, datetime)
        self.assertIsNotNone(value.tzinfo)


if __name__ == "__main__":
    unittest.main()
