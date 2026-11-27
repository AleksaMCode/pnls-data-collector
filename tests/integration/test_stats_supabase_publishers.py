"""Integration tests for the stats publishers against the Supabase schema, on Postgres 17.6."""

import json
import os
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import text

from tests.integration.containers import requires_postgres
from tests.integration.stats_db import (
    DAILY_TOTALS,
    DAY_2,
    DAY_3,
    UNIQUE_TOTALS,
    StatsDatabaseMixin,
    supabase_helpers,
)


def daily_total(day: date, ssid_count=1, mac_count=1, probes_count=1):
    return SimpleNamespace(
        date=day, ssid_count=ssid_count, mac_count=mac_count, probes_count=probes_count
    )


def company(name, country="Switzerland", alpha3="CHE", total=1, percentage=50.0):
    return SimpleNamespace(
        company=name,
        country=country,
        country_alpha3=alpha3,
        total_occurrences=total,
        percentage=percentage,
    )


@requires_postgres
class PublisherTestCase(StatsDatabaseMixin, unittest.TestCase):
    database_prefix = "stats_publishers"

    def execute(self, sql: str, **params):
        with self.supabase.begin() as connection:
            connection.execute(text(sql), params)


class TestDailyMetrics(PublisherTestCase):
    def test_daily_totals_of_every_metric(self):
        supabase_helpers.publish_ssid_all()
        supabase_helpers.public_mac_all()
        supabase_helpers.public_probes_all()

        for table, key in (
            ("daily_imports_ssid", "ssid_count"),
            ("daily_imports_mac", "mac_count"),
            ("daily_imports_probes", "probes_count"),
        ):
            with self.subTest(table=table):
                self.assertEqual(
                    self.supabase_rows(
                        f"SELECT date, count FROM {table} ORDER BY date"
                    ),
                    [(day, values[key]) for day, values in DAILY_TOTALS.items()],
                )

    def test_given_totals_are_published_instead_of_the_local_ones(self):
        supabase_helpers.publish_ssid_all(
            daily_totals=[daily_total(DAY_3, ssid_count=42)]
        )

        self.assertEqual(
            self.supabase_rows("SELECT date, count FROM daily_imports_ssid"),
            [(DAY_3, 42)],
        )

    def test_published_day_is_not_changed_by_a_later_run(self):
        supabase_helpers.publish_ssid_all(
            daily_totals=[daily_total(DAY_3, ssid_count=1)]
        )
        supabase_helpers.publish_ssid_all(
            daily_totals=[daily_total(DAY_3, ssid_count=99)]
        )

        self.assertEqual(
            self.supabase_rows("SELECT date, count FROM daily_imports_ssid"),
            [(DAY_3, 1)],
        )

    def test_published_day_is_updated_when_updates_are_allowed(self):
        supabase_helpers.publish_ssid_all(
            daily_totals=[daily_total(DAY_3, ssid_count=1)]
        )

        supabase_helpers._publish_daily_metric_all(
            supabase_helpers.DailyImportsSsid,
            "ssid_count",
            daily_totals=[daily_total(DAY_3, ssid_count=99)],
            skip_update=False,
        )

        self.assertEqual(
            self.supabase_rows("SELECT date, count FROM daily_imports_ssid"),
            [(DAY_3, 99)],
        )

    def test_day_without_the_metric_is_skipped(self):
        supabase_helpers.publish_ssid_all(
            daily_totals=[daily_total(DAY_2, ssid_count=None), daily_total(DAY_3)]
        )

        self.assertEqual(
            self.supabase_rows("SELECT date FROM daily_imports_ssid"), [(DAY_3,)]
        )


class TestDevices(PublisherTestCase):
    def test_device_locations_are_updated_from_the_local_database(self):
        supabase_helpers.publish_location_mapping_resolved_all()

        rows = dict(self.supabase_rows("SELECT device, location FROM devices"))
        self.assertEqual(rows["RPI-2"], "CERN Community Support Centre (62/R-001)")
        self.assertEqual(len(rows), 3)

    def test_new_device_is_added(self):
        self.execute("DELETE FROM devices WHERE device = 'RPI-3'")

        supabase_helpers.publish_location_mapping_resolved_all()

        self.assertEqual(self.supabase_scalar("SELECT count(*) FROM devices"), 3)


class TestDeviceDailyImports(PublisherTestCase):
    def test_one_row_per_device_for_the_day(self):
        supabase_helpers.publish_device_daily_imports_today(import_date=DAY_2)

        self.assertEqual(
            self.supabase_rows(
                "SELECT device_id, ssid, mac, probes, date FROM device_daily_imports "
                "ORDER BY device_id"
            ),
            [("RPI-1", 2, 2, 2, DAY_2), ("RPI-2", 2, 2, 3, DAY_2)],
        )

    def test_published_day_is_not_published_twice(self):
        supabase_helpers.publish_device_daily_imports_today(import_date=DAY_2)
        supabase_helpers.publish_device_daily_imports_today(import_date=DAY_2)

        self.assertEqual(
            self.supabase_scalar("SELECT count(*) FROM device_daily_imports"), 2
        )

    @unittest.expectedFailure
    def test_device_missing_from_supabase_is_reported(self):
        """Known issue: the foreign-key error for a device missing from `devices` is caught as a
        duplicate and logged at INFO as "Skipping update", so the day is silently left out. Remove
        the decorator once it is reported as an error.
        """
        self.execute("DELETE FROM devices WHERE device = 'RPI-2'")

        with self.assertLogs(supabase_helpers.logger, "WARNING"):
            supabase_helpers.publish_device_daily_imports_today(import_date=DAY_2)


class TestDeviceManufacturerStats(PublisherTestCase):
    def test_top_manufacturers_of_each_device(self):
        supabase_helpers.publish_device_manufacturer_stats_all(target_date=DAY_3)

        rows = dict(
            self.supabase_rows(
                "SELECT device_id, manufacturer_data FROM device_manufacturer_stats "
                "WHERE date = :day",
                day=DAY_3,
            )
        )
        self.assertEqual(sorted(rows), ["RPI-1", "RPI-2", "RPI-3"])
        self.assertEqual(
            [(entry["company"], entry["percentage"]) for entry in rows["RPI-2"]],
            [("Raspberry Pi Foundation", 75.0), ("Apple, Inc.", 25.0)],
        )
        # Private addresses are left out; RPI-1's only other captures are from Apple.
        self.assertEqual([entry["company"] for entry in rows["RPI-1"]], ["Apple, Inc."])
        self.assertEqual(rows["RPI-3"], [])

    @unittest.expectedFailure
    def test_rerun_for_the_same_day_does_not_duplicate_rows(self):
        """Known bug: `device_manufacturer_stats` has no unique (device_id, date). Remove the
        decorator once a rerun leaves one row per device and day.
        """
        supabase_helpers.publish_device_manufacturer_stats_all(target_date=DAY_3)
        supabase_helpers.publish_device_manufacturer_stats_all(target_date=DAY_3)

        self.assertEqual(
            self.supabase_scalar("SELECT count(*) FROM device_manufacturer_stats"), 3
        )


class TestManufacturerStats(PublisherTestCase):
    def rows(self):
        return self.supabase_rows(
            "SELECT company, country_alpha3, total_occurrences, percentage "
            "FROM manufacturer_stats ORDER BY company"
        )

    def test_summary_from_the_local_database(self):
        supabase_helpers.publish_manufacturer_stats_all()

        self.assertEqual(
            self.rows(),
            [
                ("Apple, Inc.", "USA", 5, 55.5556),
                ("Raspberry Pi Foundation", "GBR", 3, 33.3333),
            ],
        )

    def test_rerun_updates_instead_of_duplicating(self):
        supabase_helpers.publish_manufacturer_stats_all([company("Acme", total=1)])
        supabase_helpers.publish_manufacturer_stats_all(
            [company("Acme", total=7, percentage=70.0)]
        )

        self.assertEqual(self.rows(), [("Acme", "CHE", 7, 70.0)])

    def test_company_without_a_country_is_updated_too(self):
        unknown = {"country": None, "alpha3": None}
        supabase_helpers.publish_manufacturer_stats_all([company("Acme", **unknown)])
        supabase_helpers.publish_manufacturer_stats_all(
            [company("Acme", total=3, **unknown)]
        )

        self.assertEqual(self.rows(), [("Acme", None, 3, 50.0)])

    @unittest.expectedFailure
    def test_company_that_left_the_summary_is_removed(self):
        """Known bug: rows are only inserted or updated, so a company that drops out of the summary
        keeps its old numbers. Remove the decorator once the table matches the summary.
        """
        supabase_helpers.publish_manufacturer_stats_all(
            [company("Acme"), company("Initech")]
        )
        supabase_helpers.publish_manufacturer_stats_all(
            [company("Acme", percentage=100.0)]
        )

        self.assertEqual([row[0] for row in self.rows()], ["Acme"])


class TestSsidStats(PublisherTestCase):
    def rows(self):
        return self.supabase_rows(
            "SELECT ssid, seen_count, first_seen, last_seen FROM ssid_stats ORDER BY ssid"
        )

    def test_ssid_stats_from_the_local_database(self):
        supabase_helpers.publish_ssid_stats_all_batched()

        self.assertEqual(
            self.rows(),
            [
                ("CERN", 4, datetime(2026, 6, 12, 8, 0), datetime(2026, 6, 13, 11, 0)),
                (
                    "eduroam",
                    3,
                    datetime(2026, 6, 12, 8, 10),
                    datetime(2026, 6, 14, 7, 30),
                ),
                ("Home", 3, datetime(2026, 6, 12, 9, 0), datetime(2026, 6, 13, 11, 10)),
            ],
        )

    def test_only_ssids_seen_since_the_date(self):
        supabase_helpers.publish_ssid_stats_all_batched(updated_from=DAY_3)

        self.assertEqual([row[0] for row in self.rows()], ["eduroam"])

    def test_upsert_keeps_the_widest_seen_range_and_the_new_count(self):
        self.execute(
            "INSERT INTO ssid_stats (ssid, seen_count, first_seen, last_seen) "
            "VALUES ('CERN', 100, '2026-01-01 00:00', '2026-12-31 00:00')"
        )

        supabase_helpers.publish_ssid_stats_all_batched()

        self.assertEqual(
            self.rows()[0],
            ("CERN", 4, datetime(2026, 1, 1), datetime(2026, 12, 31)),
        )

    def test_rows_are_sent_in_batches(self):
        supabase_helpers.publish_ssid_stats_all_batched(batch_size=2)

        self.assertEqual(len(self.rows()), 3)

    def test_batch_size_must_be_positive(self):
        with self.assertRaises(ValueError):
            supabase_helpers.publish_ssid_stats_all_batched(batch_size=0)

    def test_nothing_to_publish(self):
        supabase_helpers.publish_ssid_stats_all_batched(ssid_stats_data=[])

        self.assertEqual(self.rows(), [])


class TestSsidGeo(PublisherTestCase):
    def setUp(self):
        super().setUp()
        supabase_helpers.publish_ssid_stats_all_batched()

    def geo(self) -> dict:
        return {
            ssid: (geo, updated)
            for ssid, geo, updated in self.supabase_rows(
                "SELECT ssid, geo, geo_updated FROM ssid_stats"
            )
        }

    def set_geo(self, ssid: str, geo, updated: date):
        self.execute(
            "UPDATE ssid_stats SET geo = CAST(:geo AS jsonb), geo_updated = :updated "
            "WHERE ssid = :ssid",
            ssid=ssid,
            geo=json.dumps(geo),
            updated=updated,
        )

    def test_first_run_publishes_every_geolocation_rounded(self):
        supabase_helpers.publish_ssid_geo()

        self.assertEqual(
            self.geo(),
            {
                "CERN": ([{"lat": 46.23, "lon": 6.05, "cc": "CHE"}], date(2026, 6, 10)),
                "eduroam": (
                    [
                        {"lat": 46.2, "lon": 6.1, "cc": "CHE"},
                        {"lat": 48.86, "lon": 2.35, "cc": "FRA"},
                    ],
                    DAY_3,
                ),
                "Home": (None, None),
            },
        )
        self.assertEqual(
            dict(self.supabase_rows("SELECT ssid, has_geo FROM ssid_stats")),
            {"CERN": True, "eduroam": True, "Home": False},
        )

    def test_daily_run_never_changes_a_published_geolocation(self):
        published = [{"lat": 1.0, "lon": 1.0, "cc": "CHE"}]
        # Older than every local point, so the watermark selects both SSIDs.
        self.set_geo("eduroam", published, date(2026, 6, 1))

        supabase_helpers.publish_ssid_geo()

        self.assertEqual(self.geo()["eduroam"], (published, date(2026, 6, 1)))
        self.assertIsNotNone(self.geo()["CERN"][0])

    def test_daily_run_only_sends_ssids_from_the_watermark_on(self):
        # The newest published geolocation is from DAY_3: CERN's (June 10) is older.
        self.set_geo("eduroam", [{"lat": 1.0, "lon": 1.0, "cc": "CHE"}], DAY_3)

        supabase_helpers.publish_ssid_geo()

        self.assertEqual(self.geo()["CERN"], (None, None))

    def test_backfill_replaces_every_geolocation(self):
        self.set_geo("eduroam", [{"lat": 1.0, "lon": 1.0, "cc": "CHE"}], DAY_3)

        supabase_helpers.publish_ssid_geo(overwrite=True)

        self.assertEqual(len(self.geo()["eduroam"][0]), 2)
        self.assertIsNotNone(self.geo()["CERN"][0])

    def test_ssid_without_a_stats_row_is_reported(self):
        self.execute("DELETE FROM ssid_stats WHERE ssid = 'CERN'")

        with self.assertLogs(supabase_helpers.logger, "WARNING") as logs:
            supabase_helpers.publish_ssid_geo()

        self.assertIn("1 SSID(s) with geolocation have no row", logs.output[-1])
        self.assertIsNotNone(self.geo()["eduroam"][0])

    def test_batch_size_must_be_positive(self):
        with self.assertRaises(ValueError):
            supabase_helpers.publish_ssid_geo(batch_size=0)


class TestUniqueTotals(PublisherTestCase):
    def test_snapshot_of_the_day(self):
        supabase_helpers.publish_unique_total_stats(target_date=DAY_3)

        self.assertEqual(
            self.supabase_rows("SELECT date, totals FROM unique_total_stats"),
            [(DAY_3, UNIQUE_TOTALS)],
        )

    @unittest.expectedFailure
    def test_rerun_for_the_same_day_keeps_one_snapshot(self):
        """Known bug: `unique_total_stats.date` has a plain index, not a unique one, so every run
        adds a row. Remove the decorator once a rerun updates the day's snapshot.
        """
        supabase_helpers.publish_unique_total_stats(target_date=DAY_3)
        supabase_helpers.publish_unique_total_stats(target_date=DAY_3)

        self.assertEqual(
            self.supabase_scalar("SELECT count(*) FROM unique_total_stats"), 1
        )


class TestMacStats(PublisherTestCase):
    def test_pepper_is_required(self):
        with mock.patch.dict(os.environ, {"MAC_HASH_PEPPER": ""}):
            with self.assertRaisesRegex(RuntimeError, "MAC_HASH_PEPPER"):
                supabase_helpers.publish_mac_stats_all_batched()

    @unittest.expectedFailure
    def test_mac_stats_can_be_published(self):
        """Known issue: `mac_stats` was dropped from Supabase, but this publisher still writes to it.
        Remove the decorator once the function is removed or the table restored.
        """
        with mock.patch.dict(os.environ, {"MAC_HASH_PEPPER": "test-pepper"}):
            supabase_helpers.publish_mac_stats_all_batched()


if __name__ == "__main__":
    unittest.main()
