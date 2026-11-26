"""End-to-end tests of POST /stats, from the seeded local database to the Supabase schema."""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.containers import requires_postgres
from tests.integration.stats_db import (
    CATCH_UP_WORKFLOW_DATES,
    DAILY_TOTALS,
    DAY_3,
    UNIQUE_TOTALS,
    StatsDatabaseMixin,
)
from tests.support.stats_loader import import_stats_module

main = import_stats_module("stats.main")


@requires_postgres
class StatsWorkflowTestCase(StatsDatabaseMixin, unittest.TestCase):
    database_prefix = "stats_workflow"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.enterClassContext(
            TestClient(main.app, raise_server_exceptions=False)
        )

    def publish(self):
        return self.client.post("/stats")


class TestStatsWorkflow(StatsWorkflowTestCase):
    def test_latest_import_is_published_to_every_table(self):
        response = self.publish()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["start_date"], DAY_3.isoformat())
        self.assertEqual(
            self.supabase_rows("SELECT date, count FROM daily_imports_probes"),
            [(DAY_3, DAILY_TOTALS[DAY_3]["probes_count"])],
        )
        self.assertEqual(
            self.supabase_rows(
                "SELECT device_id, probes, date FROM device_daily_imports"
            ),
            [("RPI-1", 1, DAY_3)],
        )
        self.assertEqual(
            self.supabase_scalar(
                "SELECT count(*) FROM device_manufacturer_stats WHERE date = :day",
                day=DAY_3,
            ),
            3,
        )
        self.assertEqual(
            self.supabase_rows(
                "SELECT company FROM manufacturer_stats ORDER BY company"
            ),
            [("Apple, Inc.",), ("Raspberry Pi Foundation",)],
        )
        self.assertEqual(
            self.supabase_rows("SELECT date, totals FROM unique_total_stats"),
            [(DAY_3, UNIQUE_TOTALS)],
        )

    def test_ssids_seen_on_the_latest_day_get_their_geolocation(self):
        self.publish()

        # Only eduroam was seen on DAY_3. CERN's geolocation waits for its stats row.
        self.assertEqual(
            self.supabase_rows("SELECT ssid, has_geo FROM ssid_stats"),
            [("eduroam", True)],
        )
        self.assertEqual(
            self.supabase_rows("SELECT jsonb_array_length(geo) FROM ssid_stats"), [(2,)]
        )

    @unittest.expectedFailure
    def test_every_day_of_the_latest_import_is_published(self):
        """Known bug: only the newest imported date is published, so DAY_2, imported in the same
        catch-up workflow as DAY_3, never reaches Supabase. Remove the decorator once publishing
        starts from the oldest date of the latest import.
        """
        self.publish()

        self.assertEqual(
            [
                row[0]
                for row in self.supabase_rows(
                    "SELECT date FROM daily_imports_ssid ORDER BY date"
                )
            ],
            list(CATCH_UP_WORKFLOW_DATES),
        )

    @unittest.expectedFailure
    def test_second_run_changes_nothing(self):
        """Known bugs: `unique_total_stats` and `device_manufacturer_stats` have no unique
        constraint, so a rerun (an orchestrator retry, say) adds a second set of rows. Remove the
        decorator once both are fixed.
        """
        self.publish()
        after_first_run = self.table_counts()

        self.publish()

        self.assertEqual(self.table_counts(), after_first_run)


@requires_postgres
class TestStatsWorkflowWithoutNewCaptures(StatsWorkflowTestCase):
    database_prefix = "stats_workflow_skipped"

    @classmethod
    def seed_local(cls):
        # The imports and geolocations stay, but there are no captures to publish.
        super().seed_local()
        with cls.local.begin() as connection:
            connection.execute(text("DELETE FROM captured_info"))

    def test_run_is_skipped_but_geolocations_are_still_published(self):
        self.execute_supabase(
            "INSERT INTO ssid_stats (ssid, seen_count, first_seen, last_seen) "
            "VALUES ('CERN', 4, '2026-06-12 08:00', '2026-06-13 11:00')"
        )

        response = self.publish()

        self.assertEqual(
            response.json(),
            {
                "status": "skipped",
                "message": "No daily totals available from 2026-06-14.",
            },
        )
        self.assertEqual(
            self.supabase_rows("SELECT ssid, has_geo FROM ssid_stats"), [("CERN", True)]
        )
        self.assertEqual(
            self.supabase_scalar("SELECT count(*) FROM daily_imports_ssid"), 0
        )

    def execute_supabase(self, sql: str):
        with self.supabase.begin() as connection:
            connection.execute(text(sql))


if __name__ == "__main__":
    unittest.main()
