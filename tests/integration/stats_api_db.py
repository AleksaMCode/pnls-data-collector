"""Shared setup for the stats API integration tests: a seeded Supabase schema and a fixed "today"."""

import gc
import json
from datetime import date
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.integration.containers import create_supabase_database
from tests.support.stats_api_loader import load_app_modules

modules = load_app_modules()
supabase_helpers = modules["core.supabase.helpers"]
app_util = modules["util.util"]

TODAY = date(2026, 6, 15)

# Daily totals: date -> (probes, mac, ssid). Today's row must never be counted as a past day.
DAILY = {
    date(2026, 5, 10): (100, 50, 40),
    date(2026, 6, 12): (30, 5, 4),
    date(2026, 6, 13): (20, 4, 3),
    date(2026, 6, 14): (10, 3, 2),
    TODAY: (999, 999, 999),
}
DEVICES = {
    "RPI-1": ("Users Office (61/R-202)", "46.23,6.04"),
    "RPI-2": ("CERN Community Support Centre (62/R-001)", None),
    "RPI-3": ("Stefan's office (31/R-009)", "46.23,6.05"),
}
# Per device and day: (ssid, mac, probes). RPI-2 has no row on June 13.
DEVICE_DAILY = {
    ("RPI-1", date(2026, 6, 12)): (2, 3, 20),
    ("RPI-1", date(2026, 6, 13)): (2, 3, 15),
    ("RPI-1", date(2026, 6, 14)): (1, 2, 10),
    ("RPI-1", TODAY): (9, 9, 999),
    ("RPI-2", date(2026, 5, 10)): (5, 5, 100),
    ("RPI-2", date(2026, 6, 12)): (2, 2, 10),
    ("RPI-2", date(2026, 6, 14)): (1, 1, 5),
}
MANUFACTURERS = (
    ("Raspberry Pi Foundation", "United Kingdom", "GBR", 3, 33.3333),
    ("Apple, Inc.", "United States", "USA", 5, 55.5556),
    ("Acme", None, None, 1, 11.1111),
)
# (device, date, manufacturer data). RPI-1's June 14 snapshot is the latest.
DEVICE_MANUFACTURERS = (
    (
        "RPI-1",
        date(2026, 6, 13),
        [{"company": "Apple, Inc.", "country": "United States"}],
    ),
    (
        "RPI-1",
        date(2026, 6, 14),
        [
            {"company": "Apple, Inc.", "country": "United States"},
            {"company": "Samsung", "country": "South Korea"},
        ],
    ),
    ("RPI-2", date(2026, 6, 14), []),
)
SSIDS = (
    # (ssid, seen_count, first_seen, last_seen, geo)
    (
        "CERN",
        5,
        "2026-06-01 08:00",
        "2026-06-14 09:00",
        [{"lat": 46.23, "lon": 6.05, "cc": "CHE"}],
    ),
    ("CERN-Guest", 1, "2026-06-10 10:00", "2026-06-10 10:00", None),
    ("eduroam", 3, "2026-06-02 08:00", "2026-06-13 18:00", None),
    ("Home_5G", 2, "2026-06-05 20:00", "2026-06-12 21:00", None),
    (
        "Cafe",
        1,
        "2026-06-11 12:00",
        "2026-06-11 12:00",
        [{"lat": 48.86, "lon": 2.35, "cc": "FRA"}],
    ),
)
UNIQUE_TOTALS = (
    (date(2026, 6, 13), {"probeRequestCount": 50, "ssidCount": 4, "macCount": 7}),
    (date(2026, 6, 14), {"probeRequestCount": 60, "ssidCount": 5, "macCount": 9}),
)

TABLES = (
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


class StatsApiDatabaseMixin:
    """Gives a test class a Supabase database (Postgres 17.6) with the rows above, read by the API.

    The rows are written before each test, so tests may change them. "Today" is TODAY in the
    readers and in the stats API's date helpers.
    """

    database_prefix = "stats_api"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supabase = create_engine(create_supabase_database(cls.database_prefix))
        cls.addClassCleanup(cls.supabase.dispose)
        for target, name, value in (
            (
                supabase_helpers,
                "_session",
                sessionmaker(bind=cls.supabase, expire_on_commit=False),
            ),
            (supabase_helpers, "today_in_tz", lambda tz: TODAY),
            # last_n_dates_excluding_today and previous_n_dates_before_last_n call it here.
            (app_util, "today_in_tz", lambda tz: TODAY),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            cls.addClassCleanup(patcher.stop)

    def setUp(self):
        super().setUp()
        # fetch_total_stats leaves a transaction open until its session is garbage collected
        # (a known bug), which would block the TRUNCATE below, or outlive the container.
        gc.collect()
        self.addCleanup(gc.collect)
        with self.supabase.begin() as connection:
            # A session left open by a reader fails the test instead of hanging the run.
            connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            connection.execute(
                text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
            )
            self.seed(connection)

    def reseed(self):
        """Puts the rows above back, for tests that change them more than once."""
        with self.supabase.begin() as connection:
            connection.execute(
                text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
            )
            self.seed(connection)

    def seed(self, connection):
        def insert(sql: str, **params):
            connection.execute(text(sql), params)

        for day, (probes, mac, ssid) in DAILY.items():
            for table, count in (
                ("daily_imports_probes", probes),
                ("daily_imports_mac", mac),
                ("daily_imports_ssid", ssid),
            ):
                insert(
                    f"INSERT INTO {table} (date, count) VALUES (:d, :c)", d=day, c=count
                )
        for device, (location, coordinates) in DEVICES.items():
            insert(
                "INSERT INTO devices (device, location, coordinates) VALUES (:d, :l, :c)",
                d=device,
                l=location,
                c=coordinates,
            )
        for (device, day), (ssid, mac, probes) in DEVICE_DAILY.items():
            insert(
                "INSERT INTO device_daily_imports (device_id, ssid, mac, probes, date) "
                "VALUES (:device, :ssid, :mac, :probes, :day)",
                device=device,
                ssid=ssid,
                mac=mac,
                probes=probes,
                day=day,
            )
        for company, country, alpha3, total, percentage in MANUFACTURERS:
            insert(
                "INSERT INTO manufacturer_stats (company, country, country_alpha3, "
                "total_occurrences, percentage) VALUES (:co, :cn, :a3, :t, :p)",
                co=company,
                cn=country,
                a3=alpha3,
                t=total,
                p=percentage,
            )
        for device, day, data in DEVICE_MANUFACTURERS:
            insert(
                "INSERT INTO device_manufacturer_stats (device_id, manufacturer_data, date) "
                "VALUES (:device, CAST(:data AS jsonb), :day)",
                device=device,
                data=json.dumps(data),
                day=day,
            )
        for ssid, seen, first, last, geo in SSIDS:
            insert(
                "INSERT INTO ssid_stats (ssid, seen_count, first_seen, last_seen, geo) "
                "VALUES (:ssid, :seen, :first, :last, CAST(:geo AS jsonb))",
                ssid=ssid,
                seen=seen,
                first=first,
                last=last,
                geo=json.dumps(geo) if geo is not None else None,
            )
        for day, totals in UNIQUE_TOTALS:
            insert(
                "INSERT INTO unique_total_stats (totals, date) VALUES (CAST(:t AS jsonb), :d)",
                t=json.dumps(totals),
                d=day,
            )

    def open_transactions(self) -> int:
        with self.supabase.connect() as connection:
            return connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND state = 'idle in transaction'"
                )
            ).scalar()

    def execute(self, sql: str, **params):
        with self.supabase.begin() as connection:
            connection.execute(text(sql), params)
