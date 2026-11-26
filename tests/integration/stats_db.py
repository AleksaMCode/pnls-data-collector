"""Shared setup for the stats integration tests: the local aggregator database and the Supabase database."""

import uuid
from datetime import date
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.integration.containers import (
    create_aggregator_database,
    create_supabase_database,
)
from tests.support.stats_loader import import_stats_module

orm_helpers = import_stats_module("stats.core.orm.helpers")
supabase_helpers = import_stats_module("stats.core.supabase.helpers")

DAY_1 = date(2026, 6, 12)
DAY_2 = date(2026, 6, 13)
DAY_3 = date(2026, 6, 14)
DEVICES = ("RPI-1", "RPI-2", "RPI-3")

# Probe requests: (day, device, ssid, mac index, time). See the expected values below.
CAPTURES = (
    (DAY_1, "RPI-1", "CERN", 1, "08:00:00"),
    (DAY_1, "RPI-1", "CERN", 2, "08:05:00"),
    (DAY_1, "RPI-1", "eduroam", 1, "08:10:00"),
    (DAY_1, "RPI-2", "Home", 4, "09:00:00"),
    (DAY_2, "RPI-1", "CERN", 3, "10:00:00"),
    (DAY_2, "RPI-1", "eduroam", 5, "10:05:00"),
    (DAY_2, "RPI-2", "CERN", 1, "11:00:00"),
    (DAY_2, "RPI-2", "Home", 4, "11:05:00"),
    (DAY_2, "RPI-2", "Home", 4, "11:10:00"),
    (DAY_3, "RPI-1", "eduroam", 2, "07:30:00"),
)
# mac index -> (address, universally administered, IEEE organisation)
MACS = {
    1: ("F0:D1:A9:00:00:01", True, "Apple, Inc."),
    2: ("F0:D1:A9:00:00:02", True, "Apple, Inc."),
    3: ("E4:F1:4C:00:00:03", True, "Private"),
    4: ("B8:27:EB:00:00:04", True, "Raspberry Pi Foundation"),
    5: ("02:00:00:00:00:05", False, None),
}
ORGANISATIONS = {
    "Apple, Inc.": ("F0D1A9", "United States"),
    "Private": ("E4F14C", None),
    "Raspberry Pi Foundation": ("B827EB", "United Kingdom"),
}
COUNTRIES = (
    ("Switzerland", "CH", "CHE", "756"),
    ("France", "FR", "FRA", "250"),
    ("United States", "US", "USA", "840"),
    ("United Kingdom", "GB", "GBR", "826"),
)
# Reduced SSID geolocations: (ssid, latitude, longitude, alpha2, created).
SSID_GEO = (
    ("CERN", 46.23457, 6.04561, "CH", date(2026, 6, 10)),
    ("eduroam", 46.20001, 6.10004, "CH", date(2026, 6, 1)),
    ("eduroam", 48.85661, 2.35222, "FR", DAY_3),
)
# The aggregator imported DAY_1 in one run, then DAY_2 and DAY_3 together (catching up).
IMPORTS = ((DAY_1, 4), (DAY_2, 5), (DAY_3, 1))
CATCH_UP_WORKFLOW_DATES = (DAY_2, DAY_3)

# Expected values, worked out from CAPTURES.
DAILY_TOTALS = {
    DAY_1: {"ssid_count": 3, "mac_count": 3, "probes_count": 4},
    DAY_2: {"ssid_count": 4, "mac_count": 4, "probes_count": 5},
    DAY_3: {"ssid_count": 1, "mac_count": 1, "probes_count": 1},
}
UNIQUE_TOTALS = {"probeRequestCount": 10, "ssidCount": 3, "macCount": 5}

SUPABASE_TABLES = (
    "daily_imports_mac",
    "daily_imports_ssid",
    "daily_imports_probes",
    "device_daily_imports",
    "device_manufacturer_stats",
    "manufacturer_stats",
    "ssid_stats",
    "unique_total_stats",
    "devices",
)


class StatsDatabaseMixin:
    """Gives a test class a local database with the seeded captures and an empty Supabase database.

    Both stats helper modules have their sessions bound to these databases. The local data is
    seeded once per class and only read; the Supabase tables are emptied before each test, and
    the three devices are added, as the production `devices` table has them.
    """

    database_prefix = "stats"
    seed_devices = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.local = create_engine(create_aggregator_database(cls.database_prefix))
        cls.supabase = create_engine(create_supabase_database(cls.database_prefix))
        cls.addClassCleanup(cls.local.dispose)
        cls.addClassCleanup(cls.supabase.dispose)
        for helpers, engine in (
            (orm_helpers, cls.local),
            (supabase_helpers, cls.supabase),
        ):
            patcher = mock.patch.object(
                helpers, "_session", sessionmaker(bind=engine, expire_on_commit=False)
            )
            patcher.start()
            cls.addClassCleanup(patcher.stop)
        cls.seed_local()

    def setUp(self):
        super().setUp()
        with self.supabase.begin() as connection:
            connection.execute(
                text(f"TRUNCATE {', '.join(SUPABASE_TABLES)} RESTART IDENTITY CASCADE")
            )
            if self.seed_devices:
                for device in DEVICES:
                    connection.execute(
                        text("INSERT INTO devices (device, location) VALUES (:d, :l)"),
                        {"d": device, "l": f"Location of {device}"},
                    )

    @classmethod
    def seed_local(cls):
        with cls.local.begin() as connection:

            def insert(sql: str, **params):
                return connection.execute(text(sql), params).scalar()

            countries = {
                name: insert(
                    "INSERT INTO country (name, alpha2, alpha3, country_code) "
                    "VALUES (:name, :alpha2, :alpha3, :code) RETURNING id",
                    name=name,
                    alpha2=alpha2,
                    alpha3=alpha3,
                    code=code,
                )
                for name, alpha2, alpha3, code in COUNTRIES
            }
            ouis = {}
            for org, (assignment, country) in ORGANISATIONS.items():
                org_id = insert(
                    "INSERT INTO ieee_mac_oui_org (name, country) VALUES (:name, :country) "
                    "RETURNING id",
                    name=org,
                    country=countries.get(country),
                )
                ouis[org] = insert(
                    "INSERT INTO ieee_mac_oui (registry, assignment, org) "
                    "VALUES ('MA-L', :assignment, :org) RETURNING id",
                    assignment=assignment,
                    org=org_id,
                )
            macs = {
                index: insert(
                    "INSERT INTO mac (mac, uaa, oui) VALUES (:mac, :uaa, :oui) RETURNING id",
                    mac=address,
                    uaa=uaa,
                    oui=ouis.get(org),
                )
                for index, (address, uaa, org) in MACS.items()
            }
            ssids = {
                name: insert(
                    "INSERT INTO ssid (ssid) VALUES (:ssid) RETURNING id", ssid=name
                )
                for name in sorted({capture[2] for capture in CAPTURES})
            }
            for day, device, ssid, mac, time in CAPTURES:
                insert(
                    "INSERT INTO captured_info (ssid, mac, location, timestamp) VALUES "
                    "(:ssid, :mac, (SELECT location_id FROM location_mapping "
                    "WHERE device = :device), :timestamp) RETURNING id",
                    ssid=ssids[ssid],
                    mac=macs[mac],
                    device=device,
                    timestamp=f"{day} {time}",
                )
            workflows = {}
            for day, captured in IMPORTS:
                key = "catch-up" if day in CATCH_UP_WORKFLOW_DATES else str(day)
                if key not in workflows:
                    workflows[key] = insert(
                        'INSERT INTO imports_workflow (id, start, "end", status) '
                        "VALUES (:id, now(), now(), 'COMPLETED') RETURNING id",
                        id=uuid.uuid4(),
                    )
                insert(
                    "INSERT INTO imports_info (timestamp, captured, workflow_id) "
                    "VALUES (:day, :captured, :workflow) RETURNING id",
                    day=day,
                    captured=captured,
                    workflow=workflows[key],
                )
            for ssid, latitude, longitude, alpha2, created in SSID_GEO:
                insert(
                    "INSERT INTO ssid_geo_reduced (ssid, latitude, longitude, country, "
                    "created_date) VALUES (:ssid, :lat, :lon, "
                    "(SELECT id FROM country WHERE alpha2 = :alpha2), :created) RETURNING id",
                    ssid=ssids[ssid],
                    lat=latitude,
                    lon=longitude,
                    alpha2=alpha2,
                    created=created,
                )
            connection.execute(
                text("REFRESH MATERIALIZED VIEW ieee_mac_oui_with_country")
            )

    # Helpers for the tests.

    def supabase_rows(self, sql: str, **params) -> list[tuple]:
        with self.supabase.connect() as connection:
            return [tuple(row) for row in connection.execute(text(sql), params)]

    def supabase_scalar(self, sql: str, **params):
        with self.supabase.connect() as connection:
            return connection.execute(text(sql), params).scalar()

    def table_counts(self) -> dict[str, int]:
        return {
            table: self.supabase_scalar(f"SELECT count(*) FROM {table}")
            for table in SUPABASE_TABLES
        }
