import importlib
import os
import unittest
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from testcontainers.postgres import PostgresContainer
except ImportError:
    PostgresContainer = None


@unittest.skipUnless(
    PostgresContainer is not None,
    "testcontainers is required for Postgres integration tests",
)
class TestOrmHelpersIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._postgres = PostgresContainer("postgres:15.18")
        cls._postgres.start()

        connection_url = cls._postgres.get_connection_url()
        parsed = urlparse(connection_url)

        os.environ["DB_USER"] = parsed.username or ""
        os.environ["DB_PASS"] = parsed.password or ""
        os.environ["DB_URL"] = parsed.hostname or ""
        os.environ["DB_PORT"] = str(parsed.port or "")
        os.environ["DB_NAME"] = parsed.path.lstrip("/")

        cls.models = importlib.import_module("aggregator.core.orm.models")
        cls.helpers = importlib.import_module("aggregator.core.orm.helpers")

        cls.engine = create_engine(connection_url, pool_pre_ping=True)
        cls.models.ImportsWorkflow.__table__.create(cls.engine, checkfirst=True)
        cls.models.DailyCapturedPerDevice.__table__.create(cls.engine, checkfirst=True)
        cls.models.Country.__table__.create(cls.engine, checkfirst=True)
        cls.models.IEEEMacOuiOrg.__table__.create(cls.engine, checkfirst=True)
        cls.models.IEEEMacOui.__table__.create(cls.engine, checkfirst=True)
        cls.models.SSID.__table__.create(cls.engine, checkfirst=True)
        cls.models.MAC.__table__.create(cls.engine, checkfirst=True)

        cls.session_factory = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        cls.helpers._session = cls.session_factory

    @classmethod
    def tearDownClass(cls):
        cls.models.MAC.__table__.drop(cls.engine, checkfirst=True)
        cls.models.SSID.__table__.drop(cls.engine, checkfirst=True)
        cls.models.IEEEMacOui.__table__.drop(cls.engine, checkfirst=True)
        cls.models.IEEEMacOuiOrg.__table__.drop(cls.engine, checkfirst=True)
        cls.models.Country.__table__.drop(cls.engine, checkfirst=True)
        cls.models.DailyCapturedPerDevice.__table__.drop(cls.engine, checkfirst=True)
        cls.models.ImportsWorkflow.__table__.drop(cls.engine, checkfirst=True)
        cls.engine.dispose()
        cls._postgres.stop()

    def setUp(self):
        with self.session_factory() as db:
            db.query(self.models.MAC).delete()
            db.query(self.models.SSID).delete()
            db.query(self.models.DailyCapturedPerDevice).delete()
            db.query(self.models.ImportsWorkflow).delete()
            db.commit()

    def test_create_import_workflow_stores_started_status(self):
        workflow_id = self.helpers.create_import_workflow()

        self.assertIsNotNone(workflow_id)
        self.assertIsInstance(workflow_id, uuid.UUID)

        with self.session_factory() as db:
            workflow = (
                db.query(self.models.ImportsWorkflow).filter_by(id=workflow_id).one()
            )
            self.assertEqual(workflow.status, self.models.WorkflowStatus.STARTED)

    def test_set_and_get_import_workflow_status(self):
        workflow_id = self.helpers.create_import_workflow()
        self.helpers.set_import_workflow_status(
            workflow_id, self.models.WorkflowStatus.COMPLETED
        )

        status = self.helpers.get_import_workflow_status(workflow_id)
        self.assertEqual(status, self.models.WorkflowStatus.COMPLETED)

    def test_get_import_workflow_status_returns_none_for_missing_workflow(self):
        missing_workflow_id = uuid.uuid4()
        status = self.helpers.get_import_workflow_status(missing_workflow_id)
        self.assertIsNone(status)

    def test_get_running_import_workflow_id_returns_started_workflow(self):
        started_workflow_id = self.helpers.create_import_workflow()
        completed_workflow_id = self.helpers.create_import_workflow()
        self.helpers.set_import_workflow_status(
            completed_workflow_id, self.models.WorkflowStatus.COMPLETED
        )

        running_workflow_id = self.helpers.get_running_import_workflow_id()

        self.assertEqual(running_workflow_id, started_workflow_id)

    def test_get_running_import_workflow_id_returns_none_without_started_workflow(self):
        workflow_id = self.helpers.create_import_workflow()
        self.helpers.set_import_workflow_status(
            workflow_id, self.models.WorkflowStatus.FAILED
        )

        running_workflow_id = self.helpers.get_running_import_workflow_id()

        self.assertIsNone(running_workflow_id)

    def test_get_today_data_from_daily_captured_stats_per_device_filters_by_import_date(
        self,
    ):
        target_date = datetime.now(ZoneInfo("UTC")).date() - timedelta(days=1)
        non_target_date = target_date - timedelta(days=1)

        with self.session_factory() as db:
            db.add_all(
                [
                    self.models.DailyCapturedPerDevice(
                        date=target_date,
                        device="RPI-1",
                        ssid=10,
                        probe_request=100,
                        mac=20,
                    ),
                    self.models.DailyCapturedPerDevice(
                        date=target_date,
                        device="RPI-2",
                        ssid=30,
                        probe_request=300,
                        mac=40,
                    ),
                    self.models.DailyCapturedPerDevice(
                        date=non_target_date,
                        device="RPI-3",
                        ssid=50,
                        probe_request=500,
                        mac=60,
                    ),
                ]
            )
            db.commit()

        rows = self.helpers.get_today_data_from_daily_captured_stats_per_device(
            tz="UTC",
            import_date=target_date,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual({row.device for row in rows}, {"RPI-1", "RPI-2"})
        self.assertTrue(all(row.date == target_date for row in rows))

    def test_get_today_data_from_daily_captured_stats_per_device_uses_today_when_no_import_date(
        self,
    ):
        today = datetime.now(ZoneInfo("UTC")).date()
        yesterday = today - timedelta(days=1)

        with self.session_factory() as db:
            db.add_all(
                [
                    self.models.DailyCapturedPerDevice(
                        date=today,
                        device="RPI-1",
                        ssid=1,
                        probe_request=11,
                        mac=2,
                    ),
                    self.models.DailyCapturedPerDevice(
                        date=yesterday,
                        device="RPI-2",
                        ssid=3,
                        probe_request=33,
                        mac=4,
                    ),
                ]
            )
            db.commit()

        rows = self.helpers.get_today_data_from_daily_captured_stats_per_device(
            tz="UTC"
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].device, "RPI-1")
        self.assertEqual(rows[0].date, today)

    def test_get_data_from_daily_captured_stats_per_device_between_dates_inclusive(
        self,
    ):
        start_date = datetime.now(ZoneInfo("UTC")).date() - timedelta(days=5)
        mid_date = start_date + timedelta(days=2)
        end_date = start_date + timedelta(days=5)

        with self.session_factory() as db:
            db.add_all(
                [
                    # Inside window: start/mid/end dates should be included.
                    self.models.DailyCapturedPerDevice(
                        date=start_date,
                        device="RPI-1",
                        ssid=10,
                        probe_request=100,
                        mac=20,
                    ),
                    self.models.DailyCapturedPerDevice(
                        date=mid_date,
                        device="RPI-2",
                        ssid=30,
                        probe_request=300,
                        mac=40,
                    ),
                    self.models.DailyCapturedPerDevice(
                        date=end_date,
                        device="RPI-3",
                        ssid=50,
                        probe_request=500,
                        mac=60,
                    ),
                    # Outside window.
                    self.models.DailyCapturedPerDevice(
                        date=start_date - timedelta(days=1),
                        device="RPI-4",
                        ssid=70,
                        probe_request=700,
                        mac=80,
                    ),
                    self.models.DailyCapturedPerDevice(
                        date=end_date + timedelta(days=1),
                        device="RPI-5",
                        ssid=90,
                        probe_request=900,
                        mac=100,
                    ),
                ]
            )
            db.commit()

        rows = self.helpers.get_data_from_daily_captured_stats_per_device_between_dates(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual({row.device for row in rows}, {"RPI-1", "RPI-2", "RPI-3"})
        self.assertTrue(all(start_date <= row.date <= end_date for row in rows))

    def test_get_data_from_daily_captured_stats_per_device_between_dates_returns_empty(
        self,
    ):
        start_date = datetime.now(ZoneInfo("UTC")).date() - timedelta(days=10)
        end_date = start_date + timedelta(days=2)

        with self.session_factory() as db:
            db.add(
                self.models.DailyCapturedPerDevice(
                    date=end_date + timedelta(days=5),
                    device="RPI-9",
                    ssid=1,
                    probe_request=2,
                    mac=3,
                )
            )
            db.commit()

        rows = self.helpers.get_data_from_daily_captured_stats_per_device_between_dates(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(rows, [])

    def test_get_or_create_ssid_id_returns_existing_id(self):
        with self.session_factory() as db:
            existing = self.models.SSID(ssid="MyWifi")
            db.add(existing)
            db.commit()
            db.refresh(existing)
            existing_id = existing.id

            resolved_id = self.helpers.get_or_create_ssid_id(db, "MyWifi")
            db.commit()

        self.assertEqual(resolved_id, existing_id)

    def test_get_or_create_ssid_id_creates_row_when_missing(self):
        with self.session_factory() as db:
            resolved_id = self.helpers.get_or_create_ssid_id(db, "NewWifi")
            db.commit()

            persisted = db.query(self.models.SSID).filter_by(ssid="NewWifi").one()

        self.assertEqual(resolved_id, persisted.id)

    def test_get_or_create_mac_id_returns_existing_id(self):
        with self.session_factory() as db:
            existing = self.models.MAC(mac="02:11:22:33:44:55")
            db.add(existing)
            db.commit()
            db.refresh(existing)
            existing_id = existing.id

            resolved_id = self.helpers.get_or_create_mac_id(db, "02:11:22:33:44:55")
            db.commit()

        self.assertEqual(resolved_id, existing_id)

    def test_get_or_create_mac_id_creates_row_when_missing(self):
        with self.session_factory() as db:
            resolved_id = self.helpers.get_or_create_mac_id(db, "06:22:33:44:55:66")
            db.commit()

            persisted = (
                db.query(self.models.MAC).filter_by(mac="06:22:33:44:55:66").one()
            )

        self.assertEqual(resolved_id, persisted.id)


if __name__ == "__main__":
    unittest.main()
