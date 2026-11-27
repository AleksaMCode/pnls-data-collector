"""Integration tests for the stats readers against the local aggregator views, on seeded captures."""

import unittest
from datetime import UTC, date, datetime
from unittest import mock

from sqlalchemy import text
from tenacity import RetryError

from tests.integration.containers import requires_postgres
from tests.integration.stats_db import (
    DAILY_TOTALS,
    DAY_1,
    DAY_2,
    DAY_3,
    UNIQUE_TOTALS,
    StatsDatabaseMixin,
    orm_helpers,
)
from tests.support.aggregator_loader import no_retry_wait
from util.core.orm.models import Device


def totals(rows) -> dict:
    return {
        row.date: {
            "ssid_count": row.ssid_count,
            "mac_count": row.mac_count,
            "probes_count": row.probes_count,
        }
        for row in rows
    }


@requires_postgres
class TestStatsReaders(StatsDatabaseMixin, unittest.TestCase):
    database_prefix = "stats_readers"

    def test_latest_import_date(self):
        self.assertEqual(orm_helpers.get_latest_import_date(), DAY_3)

    def test_daily_totals_add_up_every_device(self):
        self.assertEqual(
            totals(orm_helpers.get_daily_totals_all_devices()), DAILY_TOTALS
        )

    def test_daily_totals_from_a_date(self):
        self.assertEqual(
            list(totals(orm_helpers.get_daily_totals_all_devices(start_date=DAY_2))),
            [DAY_2, DAY_3],
        )

    def test_one_days_captures_per_device(self):
        rows = orm_helpers.get_today_data_from_daily_captured_stats_per_device(
            import_date=DAY_2
        )

        self.assertEqual(
            sorted((row.device, row.ssid, row.mac, row.probe_request) for row in rows),
            [("RPI-1", 2, 2, 2), ("RPI-2", 2, 2, 3)],
        )

    def test_today_defaults_to_the_date_in_the_given_time_zone(self):
        class FixedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                # 23:30 UTC on June 12 is already June 13 in Paris.
                return datetime(2026, 6, 12, 23, 30, tzinfo=UTC).astimezone(tz)

        for tz, day in (("UTC", DAY_1), ("Europe/Paris", DAY_2)):
            with self.subTest(tz=tz), mock.patch.object(
                orm_helpers, "datetime", FixedClock
            ):
                rows = orm_helpers.get_today_data_from_daily_captured_stats_per_device(
                    tz=tz
                )
                self.assertEqual({row.date for row in rows}, {day})

    def test_captures_between_dates(self):
        rows = orm_helpers.get_data_from_daily_captured_stats_per_device_between_dates(
            DAY_1, DAY_2
        )

        self.assertEqual(len(rows), 4)
        self.assertEqual(
            len(orm_helpers.get_all_data_from_daily_captured_stats_per_device()), 5
        )

    def test_total_captures_per_device(self):
        rpi_1 = orm_helpers.get_device_total_captured_data(Device.RPI_1)

        self.assertEqual((rpi_1.ssid, rpi_1.mac, rpi_1.probe_request), (5, 5, 6))
        self.assertIsNone(orm_helpers.get_device_total_captured_data(Device.RPI_3))

    def test_device_locations(self):
        locations = {
            row.device: row
            for row in orm_helpers.get_all_data_from_location_mapping_resolved()
        }

        self.assertEqual(sorted(locations), ["RPI-1", "RPI-2", "RPI-3"])
        self.assertEqual(
            locations["RPI-2"].location, "CERN Community Support Centre (62/R-001)"
        )
        self.assertTrue(locations["RPI-2"].coordinates.startswith("46.23"))

    def test_company_summary_leaves_out_private_addresses(self):
        summary = {
            row.company: (
                row.country_alpha3,
                row.total_occurrences,
                float(row.percentage),
            )
            for row in orm_helpers.get_all_data_from_company_capture_summary()
        }

        # 9 captures from universally administered MACs: 5 Apple, 3 Raspberry Pi, 1 Private.
        self.assertEqual(
            summary,
            {
                "Apple, Inc.": ("USA", 5, 55.5556),
                "Raspberry Pi Foundation": ("GBR", 3, 33.3333),
            },
        )

    def test_company_summary_minimum_percentage(self):
        summary = orm_helpers.get_all_data_from_company_capture_summary(
            min_percentage=50
        )

        self.assertEqual([row.company for row in summary], ["Apple, Inc."])

    def test_company_summary_by_device(self):
        rows = orm_helpers.get_all_data_from_company_capture_summary_by_device(
            Device.RPI_2
        )

        self.assertEqual(
            [
                (row.company, row.total_occurrences, float(row.percentage))
                for row in rows
            ],
            [("Raspberry Pi Foundation", 3, 75.0), ("Apple, Inc.", 1, 25.0)],
        )

    def test_company_summary_by_device_limit(self):
        rows = orm_helpers.get_all_data_from_company_capture_summary_by_device(
            Device.RPI_2, limit=1
        )

        self.assertEqual([row.company for row in rows], ["Raspberry Pi Foundation"])

    def test_ssid_first_and_last_seen(self):
        rows = {
            row.ssid: (row.seen_count, row.first_seen, row.last_seen)
            for row in orm_helpers.get_all_data_from_ssid_first_last_seen()
        }

        self.assertEqual(
            rows,
            {
                "CERN": (4, datetime(2026, 6, 12, 8, 0), datetime(2026, 6, 13, 11, 0)),
                "eduroam": (
                    3,
                    datetime(2026, 6, 12, 8, 10),
                    datetime(2026, 6, 14, 7, 30),
                ),
                "Home": (3, datetime(2026, 6, 12, 9, 0), datetime(2026, 6, 13, 11, 10)),
            },
        )

    def test_ssids_seen_since_a_date(self):
        rows = orm_helpers.get_all_data_from_ssid_first_last_seen(updated_from=DAY_3)

        self.assertEqual([row.ssid for row in rows], ["eduroam"])

    def test_macs_seen_since_a_date(self):
        rows = orm_helpers.get_all_data_from_mac_first_last_seen(updated_from=DAY_3)

        self.assertEqual(
            [(row.mac, row.seen_count) for row in rows], [("F0:D1:A9:00:00:02", 2)]
        )

    def test_every_geolocation_point(self):
        rows = orm_helpers.get_ssid_geo_reduced_rows()

        self.assertEqual(
            sorted((row.ssid, row.country_alpha3) for row in rows),
            [("CERN", "CHE"), ("eduroam", "CHE"), ("eduroam", "FRA")],
        )

    def test_recent_geolocations_come_with_every_point_of_their_ssid(self):
        rows = orm_helpers.get_ssid_geo_reduced_rows(created_from=DAY_3)

        # The older eduroam point is included, so the SSID is never published in part.
        self.assertEqual(
            sorted((row.ssid, row.created_date) for row in rows),
            [("eduroam", date(2026, 6, 1)), ("eduroam", DAY_3)],
        )

    def test_unique_totals_snapshot(self):
        self.assertEqual(orm_helpers.get_unique_totals_snapshot(), UNIQUE_TOTALS)


@requires_postgres
class TestStatsReadersWithoutImports(StatsDatabaseMixin, unittest.TestCase):
    database_prefix = "stats_no_imports"

    @classmethod
    def seed_local(cls):
        pass

    @unittest.expectedFailure
    def test_latest_import_date_is_none_before_the_first_import(self):
        """Known bug: `.first().timestamp` raises AttributeError, which is retried 10 times with
        30-90 s waits. Remove the decorator once an empty table returns None.
        """
        with no_retry_wait(orm_helpers.get_latest_import_date):
            try:
                self.assertIsNone(orm_helpers.get_latest_import_date())
            except RetryError as error:
                raise AssertionError("No import date: retried, then failed.") from error

    def test_unique_totals_snapshot_is_zero_without_captures(self):
        self.assertEqual(
            orm_helpers.get_unique_totals_snapshot(),
            {"probeRequestCount": 0, "ssidCount": 0, "macCount": 0},
        )

    def test_no_daily_totals_without_captures(self):
        with self.local.connect() as connection:
            self.assertEqual(
                connection.execute(text("SELECT count(*) FROM captured_info")).scalar(),
                0,
            )
        self.assertEqual(orm_helpers.get_daily_totals_all_devices(), [])


if __name__ == "__main__":
    unittest.main()
