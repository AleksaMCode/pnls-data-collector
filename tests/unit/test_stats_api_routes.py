"""Unit tests for the stats API routes and the SSID CSV export, with the Supabase readers replaced."""

import csv
import io
import unittest
from datetime import datetime
from unittest import mock

from fastapi.testclient import TestClient
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from tests.support.stats_api_loader import build_app, load_app_modules

modules = load_app_modules()
routes = modules["routers.stats"]
supabase_helpers = modules["core.supabase.helpers"]

# Each cached route and the reader it returns, with the arguments it passes.
CACHED_ROUTES = {
    "/stats/total": ("fetch_total_stats", {}),
    "/stats/average/daily-counts": (
        "fetch_average_daily_counts",
        {"tz": "Europe/Paris"},
    ),
    "/stats/last-30-days": (
        "fetch_last_n_days_totals",
        {"n_days": 30, "tz": "Europe/Paris"},
    ),
    "/stats/last-30-days/totals-with-series": (
        "fetch_last_n_days_totals_with_series",
        {"n_days": 30, "tz": "Europe/Paris"},
    ),
    "/stats/previous-30-days/totals": (
        "fetch_previous_n_days_totals",
        {"n_days": 30, "tz": "Europe/Paris"},
    ),
    "/stats/probe-requests-per-device": (
        "fetch_probe_requests_per_device_last_n_days",
        {"n_days": 30, "tz": "Europe/Paris"},
    ),
    "/stats/monthly-totals": ("fetch_monthly_totals_all_devices", {}),
    "/stats/series": ("fetch_all_data_series", {"tz": "Europe/Paris"}),
    "/stats/series/RPI-2": (
        "fetch_device_data_series",
        {"device_name": "RPI-2", "tz": "Europe/Paris"},
    ),
    "/stats/devices": ("fetch_total_per_device_stats", {}),
    "/stats/manufacturers": ("fetch_manufacturers_data", {}),
    "/stats/sankey": ("fetch_sankey_data", {}),
}


class RouteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main = build_app({"SERVER_ENV": "dev"})
        cls.client = TestClient(cls.main.app)

    def setUp(self):
        super().setUp()
        # A fresh cache per test. InMemoryBackend keeps its entries on the class, so they are cleared,
        # and FastAPICache.init() is a no-op once the cache is set up (by any test), so it is reset.
        InMemoryBackend._store.clear()
        FastAPICache.reset()
        FastAPICache.init(InMemoryBackend(), prefix="test")
        self.addCleanup(FastAPICache.reset)
        self.readers = {}
        for name in {reader for reader, _ in CACHED_ROUTES.values()} | {
            "fetch_ssid_stats",
            "fetch_ssid_export_rows",
        }:
            patcher = mock.patch.object(routes, name, return_value={"reader": name})
            self.readers[name] = patcher.start()
            self.addCleanup(patcher.stop)


class TestCachedRoutes(RouteTestCase):
    def test_each_route_returns_its_reader_with_the_service_time_zone(self):
        for path, (reader, arguments) in CACHED_ROUTES.items():
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"reader": reader})
                self.readers[reader].assert_called_once_with(**arguments)

    def test_second_request_is_served_from_the_cache(self):
        self.client.get("/stats/total")
        self.readers["fetch_total_stats"].return_value = {"reader": "changed"}

        response = self.client.get("/stats/total")

        self.assertEqual(response.json(), {"reader": "fetch_total_stats"})
        self.readers["fetch_total_stats"].assert_called_once()

    def test_no_cache_header_skips_the_cache(self):
        self.client.get("/stats/total")

        self.client.get("/stats/total", headers={"Cache-Control": "no-cache"})

        self.assertEqual(self.readers["fetch_total_stats"].call_count, 2)

    def test_probe_requests_per_device_takes_the_number_of_days(self):
        self.client.get("/stats/probe-requests-per-device", params={"n_days": 7})

        self.readers[
            "fetch_probe_requests_per_device_last_n_days"
        ].assert_called_once_with(n_days=7, tz="Europe/Paris")

    def test_number_of_days_is_limited_to_a_year(self):
        for n_days in (0, 366, "many"):
            with self.subTest(n_days=n_days):
                response = self.client.get(
                    "/stats/probe-requests-per-device", params={"n_days": n_days}
                )

                self.assertEqual(response.status_code, 422)

    def test_unknown_device_is_rejected(self):
        response = self.client.get("/stats/series/RPI-9")

        self.assertEqual(response.status_code, 422)
        self.readers["fetch_device_data_series"].assert_not_called()

    def test_health(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})


class TestSsidRoutes(RouteTestCase):
    def test_ssid_list_defaults(self):
        self.client.get("/stats/ssids")

        self.readers["fetch_ssid_stats"].assert_called_once_with(
            offset=0, limit=100, sort_by="last_seen", sort_order="desc", search=None
        )

    def test_ssid_list_parameters(self):
        self.client.get(
            "/stats/ssids",
            params={
                "search": "cern",
                "sort_by": "has_geo",
                "sort_order": "asc",
                "offset": 200,
                "limit": 50,
            },
        )

        self.readers["fetch_ssid_stats"].assert_called_once_with(
            offset=200, limit=50, sort_by="has_geo", sort_order="asc", search="cern"
        )

    def test_ssid_list_is_not_cached(self):
        self.client.get("/stats/ssids")
        self.client.get("/stats/ssids")

        self.assertEqual(self.readers["fetch_ssid_stats"].call_count, 2)

    def test_invalid_ssid_list_parameters_are_rejected(self):
        for params in (
            {"sort_by": "geo"},
            {"sort_order": "up"},
            {"offset": -1},
            {"limit": 0},
            {"limit": 1001},
        ):
            with self.subTest(params=params):
                response = self.client.get("/stats/ssids", params=params)

                self.assertEqual(response.status_code, 422)


class TestSsidExport(RouteTestCase):
    def export(self, rows, **params):
        self.readers["fetch_ssid_export_rows"].return_value = rows
        return self.client.get("/stats/ssids/export", params=params)

    def rows(self, response) -> list[dict]:
        return list(csv.DictReader(io.StringIO(response.text)))

    def test_csv_columns_and_rows(self):
        response = self.export(
            [
                {
                    "ssid": "CERN",
                    "seen_count": 5,
                    "first_seen": datetime(2026, 6, 1, 8, 0),
                    "last_seen": datetime(2026, 6, 14, 9, 30),
                }
            ]
        )

        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertEqual(
            self.rows(response),
            [
                {
                    "ssid": "CERN",
                    "seen_count": "5",
                    "first_seen": "2026-06-01 08:00:00",
                    "last_seen": "2026-06-14 09:30:00",
                }
            ],
        )

    def test_missing_values_are_empty(self):
        response = self.export([{"ssid": None, "first_seen": None, "last_seen": None}])

        self.assertEqual(
            self.rows(response),
            [{"ssid": "", "seen_count": "0", "first_seen": "", "last_seen": ""}],
        )

    def test_empty_export_has_the_header(self):
        response = self.export([])

        self.assertEqual(response.text.strip(), "ssid,seen_count,first_seen,last_seen")

    def test_file_is_named_after_the_day(self):
        class FixedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 6, 15, 10, 0)

        with mock.patch.object(routes, "datetime", FixedClock):
            response = self.export([])

        self.assertEqual(
            response.headers["content-disposition"],
            'attachment; filename="ssid_stats_2026-06-15.csv"',
        )

    def test_filters_and_order_are_passed_on(self):
        self.export([], search="cern", sort_by="seen_count", sort_order="asc")

        self.readers["fetch_ssid_export_rows"].assert_called_once_with(
            sort_by="seen_count", sort_order="asc", search="cern"
        )

    @unittest.expectedFailure
    def test_ssid_that_looks_like_a_formula_is_exported_as_text(self):
        """Known bug: SSIDs are chosen by whoever sends the probe request, and a value starting
        with `=`, `+`, `-` or `@` runs as a formula in Excel. Remove the decorator once such
        values are prefixed with `'`.
        """
        formulas = [
            '=HYPERLINK("https://evil.example","x")',
            "+1+1",
            "-2+3",
            "@SUM(A1)",
        ]

        response = self.export(
            [{"ssid": formula, "seen_count": 1} for formula in formulas]
        )

        for row in self.rows(response):
            with self.subTest(ssid=row["ssid"]):
                self.assertTrue(row["ssid"].startswith("'"))


class TestSsidSortOrder(unittest.TestCase):
    def test_has_geo_sort_has_tie_breakers(self):
        order = supabase_helpers._ssid_stats_order_by("has_geo", "desc")

        self.assertEqual(
            [column.element.name for column in order], ["has_geo", "last_seen", "ssid"]
        )

    @unittest.expectedFailure
    def test_every_sort_ends_with_the_unique_ssid(self):
        """Known bug: only the `has_geo` sort has tie-breakers, so pages sorted by a column with
        ties (`seen_count`, the dates) can repeat or skip SSIDs. Remove the decorator once every
        sort ends with `ssid`.
        """
        for sort_by in ("seen_count", "first_seen", "last_seen"):
            with self.subTest(sort_by=sort_by):
                order = supabase_helpers._ssid_stats_order_by(sort_by, "desc")

                self.assertEqual(order[-1].element.name, "ssid")


if __name__ == "__main__":
    unittest.main()
