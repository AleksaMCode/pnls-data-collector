import importlib
import os
import unittest
import uuid
from urllib.parse import urlparse

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

        cls.session_factory = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        cls.helpers._session = cls.session_factory

    @classmethod
    def tearDownClass(cls):
        cls.models.ImportsWorkflow.__table__.drop(cls.engine, checkfirst=True)
        cls.engine.dispose()
        cls._postgres.stop()

    def setUp(self):
        with self.session_factory() as db:
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


if __name__ == "__main__":
    unittest.main()
