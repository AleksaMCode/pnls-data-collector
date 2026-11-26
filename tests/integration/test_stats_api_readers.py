"""Integration tests for the stats API readers against the Supabase schema, on Postgres 17.6."""

import unittest
from datetime import datetime

from tests.integration.containers import requires_postgres
from tests.integration.stats_api_db import StatsApiDatabaseMixin, supabase_helpers


@requires_postgres
class ReaderTestCase(StatsApiDatabaseMixin, unittest.TestCase):
    database_prefix = "stats_api_readers"


class TestDailyTotals(ReaderTestCase):
    def test_last_30_days_leave_out_today_and_older_days(self):
        self.assertEqual(
            supabase_helpers.fetch_last_n_days_totals(n_days=30),
            {"macCount": 12, "probeRequestCount": 60, "ssidCount": 9},
        )

    def test_last_30_days_with_a_series_per_day(self):
        result = supabase_helpers.fetch_last_n_days_totals_with_series(n_days=30)

        self.assertEqual(
            result["totals"], {"macCount": 12, "probeRequestCount": 60, "ssidCount": 9}
        )
        probes = result["series"]["probeRequestCount"]
        self.assertEqual(len(probes), 30)
        # Oldest first: June 12, 13 and 14 end the series.
        self.assertEqual(probes[-3:], [30, 20, 10])
        self.assertEqual(sum(probes[:-3]), 0)

    def test_previous_30_days(self):
        self.assertEqual(
            supabase_helpers.fetch_previous_n_days_totals(n_days=30),
            {"totals": {"macCount": 50, "probeRequestCount": 100, "ssidCount": 40}},
        )

    def test_averages_of_the_days_before_today(self):
        self.assertEqual(
            supabase_helpers.fetch_average_daily_counts(),
            {"macCount": 16, "probeRequestCount": 40, "ssidCount": 12},
        )

    def test_no_days_no_totals(self):
        self.execute(
            "TRUNCATE daily_imports_mac, daily_imports_probes, daily_imports_ssid"
        )

        self.assertEqual(
            supabase_helpers.fetch_last_n_days_totals(n_days=30),
            {"macCount": 0, "probeRequestCount": 0, "ssidCount": 0},
        )
        self.assertEqual(
            supabase_helpers.fetch_average_daily_counts(),
            {"macCount": 0, "probeRequestCount": 0, "ssidCount": 0},
        )


class TestSeries(ReaderTestCase):
    def test_series_of_every_day_before_today(self):
        self.assertEqual(
            supabase_helpers.fetch_all_data_series(),
            {
                "macCount": [50, 5, 4, 3],
                "probeRequestCount": [100, 30, 20, 10],
                "ssidCount": [40, 4, 3, 2],
                "dates": ["2026-05-10", "2026-06-12", "2026-06-13", "2026-06-14"],
                "dayCounts": 4,
            },
        )

    def test_device_series_fills_missing_days_with_zero(self):
        result = supabase_helpers.fetch_device_data_series("RPI-2")

        self.assertEqual(result["probeRequestCount"], [100, 10, 0, 5])
        self.assertEqual(result["macCount"], [5, 2, 0, 1])
        self.assertEqual(len(result["dates"]), 4)

    def test_device_without_imports_has_a_zero_series(self):
        result = supabase_helpers.fetch_device_data_series("RPI-3")

        self.assertEqual(result["probeRequestCount"], [0, 0, 0, 0])

    def test_no_imports_no_series(self):
        self.execute("TRUNCATE device_daily_imports")

        self.assertEqual(
            supabase_helpers.fetch_all_data_series(),
            {
                "macCount": [],
                "probeRequestCount": [],
                "ssidCount": [],
                "dates": [],
                "dayCounts": 0,
            },
        )

    def test_probe_requests_per_device_over_the_last_days(self):
        self.assertEqual(
            supabase_helpers.fetch_probe_requests_per_device_last_n_days(n_days=30),
            {"RPI-1": [20, 15, 10], "RPI-2": [100, 10, 5]},
        )

    @unittest.expectedFailure
    def test_probe_requests_per_device_are_aligned_by_day(self):
        """Known bug: a device's list only has the days it has rows for, so RPI-2's June 14 value
        moves to June 13. Remove the decorator once missing days are filled with 0.
        """
        result = supabase_helpers.fetch_probe_requests_per_device_last_n_days(n_days=3)

        self.assertEqual(result["RPI-2"], [10, 0, 5])

    def test_monthly_totals(self):
        self.assertEqual(
            supabase_helpers.fetch_monthly_totals_all_devices(),
            {
                "2026-05": {"probe_requests": 100, "ssid": 5, "mac": 5},
                "2026-06": {"probe_requests": 1059, "ssid": 17, "mac": 20},
            },
        )


class TestDevicesAndManufacturers(ReaderTestCase):
    def test_totals_and_location_of_every_device(self):
        result = supabase_helpers.fetch_total_per_device_stats()

        self.assertEqual(
            result["RPI-1"],
            {
                "mac": 17,
                "probe_requests": 1044,
                "ssid": 14,
                "location": "Users Office (61/R-202)",
                "coordinates": "46.23,6.04",
            },
        )
        self.assertEqual(result["RPI-2"]["probe_requests"], 115)
        self.assertIsNone(result["RPI-2"]["coordinates"])
        self.assertEqual(
            result["RPI-3"],
            {
                "mac": 0,
                "probe_requests": 0,
                "ssid": 0,
                "location": "Stefan's office (31/R-009)",
                "coordinates": "46.23,6.05",
            },
        )

    def test_manufacturers_most_seen_first(self):
        self.assertEqual(
            supabase_helpers.fetch_manufacturers_data(),
            [
                {
                    "company": "Apple, Inc.",
                    "country": "USA",
                    "count": 5,
                    "percentage": 55.5556,
                },
                {
                    "company": "Raspberry Pi Foundation",
                    "country": "GBR",
                    "count": 3,
                    "percentage": 33.3333,
                },
                {"company": "Acme", "country": None, "count": 1, "percentage": 11.1111},
            ],
        )

    def test_sankey_uses_the_latest_snapshot_of_each_device(self):
        self.assertEqual(
            supabase_helpers.fetch_sankey_data(),
            {
                "RPI-1": {
                    "Apple, Inc.": {"country": "United States"},
                    "Samsung": {"country": "South Korea"},
                },
                "RPI-2": {},
            },
        )


class TestTotalStats(ReaderTestCase):
    def test_totals_from_the_latest_snapshot_and_the_tables(self):
        self.assertEqual(
            supabase_helpers.fetch_total_stats(),
            {"macCount": 9, "ssidCount": 5, "probeRequestCount": 1159},
        )

    def test_without_a_snapshot_macs_are_added_up_per_day(self):
        self.execute("TRUNCATE unique_total_stats")

        self.assertEqual(supabase_helpers.fetch_total_stats()["macCount"], 1061)

    def test_without_ssid_stats_ssids_are_added_up_per_day(self):
        self.execute("TRUNCATE ssid_stats")

        self.assertEqual(supabase_helpers.fetch_total_stats()["ssidCount"], 1048)

    @unittest.expectedFailure
    def test_fallback_leaves_no_transaction_open(self):
        """Known bug: the fallback queries run on the session after its `with` block closed it, so
        a pooled connection stays "idle in transaction" (holding its locks) until the session is
        garbage collected. Remove the decorator once the queries run inside the block.
        """
        self.execute("TRUNCATE unique_total_stats")

        supabase_helpers.fetch_total_stats()

        self.assertEqual(self.open_transactions(), 0)


class TestSsidStats(ReaderTestCase):
    def names(self, result) -> list[str]:
        return [item["ssid"] for item in result["items"]]

    def test_most_recently_seen_first_by_default(self):
        result = supabase_helpers.fetch_ssid_stats()

        self.assertEqual(
            self.names(result), ["CERN", "eduroam", "Home_5G", "Cafe", "CERN-Guest"]
        )
        self.assertEqual(result["pagination"], {"offset": 0, "limit": 100, "total": 5})
        self.assertEqual(
            result["sorting"], {"sort_by": "last_seen", "sort_order": "desc"}
        )

    def test_items_carry_their_geolocation(self):
        cern = supabase_helpers.fetch_ssid_stats()["items"][0]

        self.assertEqual(
            cern,
            {
                "ssid": "CERN",
                "seen_count": 5,
                "first_seen": datetime(2026, 6, 1, 8, 0),
                "last_seen": datetime(2026, 6, 14, 9, 0),
                "has_geo": True,
                "geo": [{"lat": 46.23, "lon": 6.05, "cc": "CHE"}],
            },
        )

    def test_search_ignores_case(self):
        result = supabase_helpers.fetch_ssid_stats(search="cern")

        self.assertEqual(self.names(result), ["CERN", "CERN-Guest"])
        self.assertEqual(result["pagination"]["total"], 2)

    def test_ssids_with_a_geolocation_first(self):
        result = supabase_helpers.fetch_ssid_stats(sort_by="has_geo", sort_order="desc")

        self.assertEqual(
            self.names(result), ["CERN", "Cafe", "eduroam", "Home_5G", "CERN-Guest"]
        )

    def test_pages(self):
        result = supabase_helpers.fetch_ssid_stats(offset=1, limit=2)

        self.assertEqual(self.names(result), ["eduroam", "Home_5G"])
        self.assertEqual(result["pagination"], {"offset": 1, "limit": 2, "total": 5})

    @unittest.expectedFailure
    def test_underscore_in_the_search_is_a_plain_character(self):
        """Known bug: `%` and `_` are not escaped in the ILIKE pattern, so "_" matches every SSID.
        Remove the decorator once the search is escaped.
        """
        self.assertEqual(
            self.names(supabase_helpers.fetch_ssid_stats(search="_")), ["Home_5G"]
        )

    def test_export_rows_have_no_geolocation(self):
        rows = supabase_helpers.fetch_ssid_export_rows(
            sort_by="first_seen", sort_order="asc"
        )

        self.assertEqual(
            [row["ssid"] for row in rows],
            ["CERN", "eduroam", "Home_5G", "CERN-Guest", "Cafe"],
        )
        self.assertEqual(
            sorted(rows[0]), ["first_seen", "last_seen", "seen_count", "ssid"]
        )

    def test_export_rows_can_be_searched(self):
        rows = supabase_helpers.fetch_ssid_export_rows(search="guest")

        self.assertEqual([row["ssid"] for row in rows], ["CERN-Guest"])


if __name__ == "__main__":
    unittest.main()
