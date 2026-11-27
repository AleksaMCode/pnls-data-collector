"""Shared setup for the aggregator integration tests that use the full database schema."""

import importlib
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

import tests.support.aggregator_loader  # noqa: F401  Sets the DB_* variables the modules need.
from tests.integration.containers import (
    create_aggregator_database,
    redis_client,
    set_db_env,
)

# Rows the tests create. The reference data from the migrations (locations, device mappings,
# Wi-Fi channels) is kept.
TEST_DATA_TABLES = (
    "captured_info",
    "mac",
    "ssid",
    "imports_info",
    "imports_workflow",
    "ieee_mac_oui",
    "ieee_mac_oui_org",
    "country",
)


class AggregatorDatabaseMixin:
    """Gives a test class its own database with the real aggregator schema.

    The aggregator's own SessionFactory is bound to that database, so the session listeners in
    aggregator/core/orm/event.py run as in production. The Redis cache client of the helpers is
    pointed at the given logical database of the shared Redis container.
    """

    database_prefix = "aggregator"
    cache_redis_db: int

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection_url = create_aggregator_database(cls.database_prefix)
        set_db_env(cls.connection_url)

        cls.runtime = importlib.import_module("aggregator.core.orm._init_runtime")
        cls.models = importlib.import_module("aggregator.core.orm.models")
        cls.helpers = importlib.import_module("aggregator.core.orm.helpers")
        cls.redis_helpers = importlib.import_module("aggregator.core.redis.helpers")
        importlib.import_module("aggregator.core.orm.event")

        cls.engine = create_engine(cls.connection_url)
        cls.session_factory = cls.runtime.SessionFactory
        cls._original_bind = cls.session_factory.kw.get("bind")
        cls.session_factory.configure(bind=cls.engine)
        cls._original_session = cls.helpers._session
        cls.helpers._session = cls.session_factory

        cls._original_redis_client = cls.redis_helpers.client
        cls.cache = redis_client(db=cls.cache_redis_db)
        cls.redis_helpers.client = cls.cache

    @classmethod
    def tearDownClass(cls):
        cls.redis_helpers.client = cls._original_redis_client
        cls.cache.close()
        cls.helpers._session = cls._original_session
        cls.session_factory.configure(bind=cls._original_bind)
        cls.engine.dispose()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.cache.flushdb()
        with self.engine.begin() as connection:
            connection.execute(
                text(f"TRUNCATE {', '.join(TEST_DATA_TABLES)} RESTART IDENTITY CASCADE")
            )
            connection.execute(
                text("REFRESH MATERIALIZED VIEW ieee_mac_oui_with_country")
            )

    # Helpers for the tests.

    def today(self) -> date:
        """Today in the aggregator's timezone, which decides the pending import dates."""
        return datetime.now(ZoneInfo(self.helpers.TIMEZONE)).date()

    def add(self, *objects):
        with self.session_factory() as db:
            db.add_all(objects)
            db.commit()
        return objects

    def scalar(self, sql: str, **params):
        with self.engine.connect() as connection:
            return connection.execute(text(sql), params).scalar()

    def rows(self, sql: str, **params):
        with self.engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(sql), params)]

    def refresh_oui_view(self):
        with self.engine.begin() as connection:
            connection.execute(
                text("REFRESH MATERIALIZED VIEW ieee_mac_oui_with_country")
            )

    def location_id(self, device: str) -> int:
        return self.scalar(
            "SELECT location_id FROM location_mapping WHERE device = :device",
            device=device,
        )
