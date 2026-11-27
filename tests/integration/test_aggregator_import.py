"""Integration tests for the aggregator database helpers on the real schema from the migrations."""

import unittest
import uuid
from datetime import timedelta
from unittest import mock

from tests.integration.aggregator_db import AggregatorDatabaseMixin
from tests.integration.containers import (
    REDIS_DB_ORM_CACHE,
    requires_postgres,
    requires_redis,
)
from tests.support.aggregator_loader import no_retry_wait
from util.core.orm.models import Device


def probe(mac="00:1A:2B:00:00:01", ssid="CERN", device="RPI-1", channel=6, **overrides):
    record = {
        "device": device,
        "mac": mac,
        "ssid": ssid,
        "channel": channel,
        "timestamp": "2026-06-14 08:00:00.000000",
    }
    record.update(overrides)
    return record


@requires_postgres
@requires_redis
class AggregatorImportTestCase(AggregatorDatabaseMixin, unittest.TestCase):
    database_prefix = "aggregator_import"
    cache_redis_db = REDIS_DB_ORM_CACHE

    def setUp(self):
        super().setUp()
        # import_data refuses to run twice a day, based on the latest imports_info row.
        self.add(
            self.models.ImportsInfo(
                timestamp=self.today() - timedelta(days=3), captured=0
            )
        )

    def import_data(self, records, **kwargs):
        return self.helpers.import_data(records, **kwargs)

    def captured_count(self) -> int:
        return self.scalar("SELECT count(*) FROM captured_info")


class TestImportData(AggregatorImportTestCase):
    def test_imports_probe_requests(self):
        imported = self.import_data(
            [
                probe("00:1A:2B:00:00:01", "CERN", channel=1),
                probe("00:1A:2B:00:00:02", "CERN", device="RPI-2", channel=11),
            ]
        )

        self.assertEqual(imported, 2)
        self.assertEqual(
            self.rows(
                "SELECT s.ssid, m.mac, c.location, c.channel, c.timestamp::text "
                "FROM captured_info c JOIN ssid s ON s.id = c.ssid "
                "JOIN mac m ON m.id = c.mac ORDER BY c.id"
            ),
            [
                (
                    "CERN",
                    "00:1A:2B:00:00:01",
                    self.location_id("RPI-1"),
                    1,
                    "2026-06-14 08:00:00",
                ),
                (
                    "CERN",
                    "00:1A:2B:00:00:02",
                    self.location_id("RPI-2"),
                    11,
                    "2026-06-14 08:00:00",
                ),
            ],
        )

    def test_ssids_and_macs_are_stored_once(self):
        self.import_data([probe(), probe(), probe(mac="00:1A:2B:00:00:09")])

        self.assertEqual(self.captured_count(), 3)
        self.assertEqual(self.scalar("SELECT count(*) FROM ssid"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM mac"), 2)

    def test_ids_are_cached_in_redis(self):
        self.import_data([probe("00:1A:2B:00:00:01", "CERN")])

        ssid_id = self.scalar("SELECT id FROM ssid WHERE ssid = 'CERN'")
        mac_id = self.scalar("SELECT id FROM mac")
        self.assertEqual(self.cache.get("ssid:id:CERN"), str(ssid_id))
        self.assertEqual(self.cache.get("mac:id:00:1a:2b:00:00:01"), str(mac_id))

    def test_records_the_import_with_its_date_and_workflow(self):
        workflow_id = self.helpers.create_import_workflow()
        import_date = self.today() - timedelta(days=2)

        self.import_data(
            [probe(), probe()], manual_import_date=import_date, workflow_id=workflow_id
        )

        self.assertEqual(
            self.rows(
                "SELECT timestamp, captured, workflow_id::text FROM imports_info "
                "WHERE workflow_id IS NOT NULL"
            ),
            [(import_date, 2, str(workflow_id))],
        )

    def test_local_import_records_no_import_row(self):
        self.import_data([probe()], firebase_import=False)

        self.assertEqual(self.captured_count(), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM imports_info"), 1)

    def test_invalid_records_are_skipped(self):
        valid = probe("00:1A:2B:00:00:01")
        cases = {
            "channel out of range": probe(channel=15),
            "channel not a number": probe(channel="x"),
            "empty ssid": probe(ssid=""),
            "ssid of control characters only": probe(ssid="\x00\x1f"),
            "missing mac": probe(mac=None),
            "missing timestamp": probe(timestamp=None),
            "device without location": probe(device="RPI-9"),
        }
        for name, record in cases.items():
            with self.subTest(name):
                self.setUp()  # Starts every case from empty tables.

                imported = self.import_data([record, valid])

                self.assertEqual(imported, 1)
                self.assertEqual(self.captured_count(), 1)

    def test_filtered_macs_are_skipped(self):
        with mock.patch.object(
            self.helpers.settings, "MAC_FILTER", ["00:1A:2B:00:00:01"]
        ):
            imported = self.import_data(
                [probe("00:1A:2B:00:00:01"), probe("00:1A:2B:00:00:02")]
            )

        self.assertEqual(imported, 1)
        self.assertEqual(self.scalar("SELECT mac FROM mac"), "00:1A:2B:00:00:02")

    def test_second_import_on_the_same_day_is_refused(self):
        self.add(self.models.ImportsInfo(timestamp=self.today(), captured=5))

        self.assertEqual(self.import_data([probe()]), 0)
        self.assertEqual(self.captured_count(), 0)

    def test_bad_record_rolls_back_the_whole_batch(self):
        imported = self.import_data([probe(), probe(timestamp="14/06/2026 08:00")])

        self.assertEqual(imported, 0)
        self.assertEqual(self.captured_count(), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM ssid"), 0)

    @unittest.expectedFailure
    def test_record_without_ssid_is_skipped(self):
        """Known bug: clean_string(None) raises before the missing-value check, so one record
        without an SSID rolls back the whole import. Remove the decorator once it is skipped.
        """
        self.assertEqual(self.import_data([probe(ssid=None), probe()]), 1)


class TestLatestImportDate(AggregatorImportTestCase):
    def test_returns_the_most_recent_import(self):
        self.add(self.models.ImportsInfo(timestamp=self.today() - timedelta(days=1)))

        self.assertEqual(
            self.helpers.get_latest_import_date(), self.today() - timedelta(days=1)
        )

    @unittest.expectedFailure
    def test_empty_table_returns_none(self):
        """Known bug: `.first().timestamp` raises on an empty table, and the @retry decorator
        then waits up to 15 minutes before giving up. Remove the decorator once it returns None.
        """
        with self.engine.begin() as connection:
            connection.exec_driver_sql("TRUNCATE imports_info")

        with no_retry_wait(self.helpers.get_latest_import_date):
            self.assertIsNone(self.helpers.get_latest_import_date())


class TestResolveOui(AggregatorImportTestCase):
    def setUp(self):
        super().setUp()
        models = self.models
        self.add(
            models.Country(
                id=1, name="Switzerland", alpha2="CH", alpha3="CHE", country_code="756"
            )
        )
        self.add(
            models.IEEEMacOuiOrg(id=1, name="Large Org", country=1),
            models.IEEEMacOuiOrg(id=2, name="Medium Org"),
            models.IEEEMacOuiOrg(id=3, name="Small Org"),
            models.IEEEMacOuiOrg(id=4, name="Not CERN"),
            models.IEEEMacOuiOrg(id=5, name="CERN"),
        )
        self.add(
            models.IEEEMacOui(id=10, registry="MA-L", assignment="001A2B", org=1),
            models.IEEEMacOui(id=11, registry="MA-M", assignment="001A2B3", org=2),
            models.IEEEMacOui(id=12, registry="MA-S", assignment="001A2B3C4", org=3),
            models.IEEEMacOui(id=20, registry="MA-L", assignment="0050C2", org=1),
            # The IEEE data lists 08:00:30 twice; the aggregator must pick CERN.
            models.IEEEMacOui(id=30, registry="MA-L", assignment="080030", org=4),
            models.IEEEMacOui(id=31, registry="MA-L", assignment="080030", org=5),
        )
        self.refresh_oui_view()

    def resolve(self, mac_address: str, **kwargs):
        mac = self.models.MAC(mac=mac_address, **kwargs)
        with self.session_factory() as db:
            self.helpers.resolve_oui(db, mac)
        return mac.oui

    def test_most_specific_registry_wins(self):
        cases = {
            "00:1A:2B:3C:4D:5E": 12,  # MA-S, MA-M and MA-L all match.
            "00:1A:2B:3F:00:00": 11,  # MA-M and MA-L match.
            "00:1A:2B:00:00:00": 10,  # Only MA-L matches.
            "00:50:C2:11:22:33": 20,
        }
        for mac_address, oui_id in cases.items():
            with self.subTest(mac=mac_address):
                self.assertEqual(self.resolve(mac_address), oui_id)

    def test_duplicate_cern_assignment_resolves_to_cern(self):
        self.assertEqual(self.resolve("08:00:30:00:00:01"), 31)

    def test_unknown_prefix_has_no_oui(self):
        self.assertIsNone(self.resolve("00:99:99:00:00:01"))

    def test_locally_administered_mac_is_not_looked_up(self):
        # The second bit of the first byte marks a randomized, locally administered MAC.
        self.assertIsNone(self.resolve("02:1A:2B:3C:4D:5E"))

    def test_existing_oui_is_kept(self):
        self.assertEqual(self.resolve("00:1A:2B:3C:4D:5E", oui=20), 20)

    def test_import_stores_the_oui_of_new_macs(self):
        self.import_data([probe("00:1A:2B:3C:4D:5E"), probe("02:00:00:00:00:01")])

        self.assertEqual(
            self.rows("SELECT mac, uaa, oui FROM mac ORDER BY mac"),
            [("00:1A:2B:3C:4D:5E", True, 12), ("02:00:00:00:00:01", False, None)],
        )


class TestSessionListeners(AggregatorImportTestCase):
    """The listeners in aggregator/core/orm/event.py, on the aggregator's own SessionFactory."""

    def test_new_mac_gets_its_oui_on_commit(self):
        self.add(self.models.IEEEMacOuiOrg(id=1, name="Org"))
        self.add(
            self.models.IEEEMacOui(id=10, registry="MA-L", assignment="001A2B", org=1)
        )
        self.refresh_oui_view()

        self.add(self.models.MAC(mac="00:1A:2B:00:00:01"))

        self.assertEqual(self.scalar("SELECT oui FROM mac"), 10)

    def test_finished_workflow_gets_an_end_time(self):
        completed = self.helpers.create_import_workflow()
        running = self.helpers.create_import_workflow()

        self.helpers.set_import_workflow_status(
            completed, self.models.WorkflowStatus.COMPLETED
        )

        ends = dict(self.rows('SELECT id::text, "end" FROM imports_workflow'))
        self.assertIsNotNone(ends[str(completed)])
        self.assertIsNone(ends[str(running)])

    def test_status_of_unknown_workflow_is_ignored(self):
        self.helpers.set_import_workflow_status(
            uuid.uuid4(), self.models.WorkflowStatus.COMPLETED
        )

        self.assertEqual(self.scalar("SELECT count(*) FROM imports_workflow"), 0)


class TestReadHelpers(AggregatorImportTestCase):
    """Queries over the totals and the database views, after a real import."""

    def setUp(self):
        super().setUp()
        self.day = self.today() - timedelta(days=2)
        timestamp = f"{self.day} 08:00:00.000000"
        self.import_data(
            [
                probe("00:1A:2B:00:00:01", "CERN", timestamp=timestamp),
                probe("00:1A:2B:00:00:02", "CERN", timestamp=timestamp),
                probe("00:1A:2B:00:00:01", "eduroam", "RPI-2", timestamp=timestamp),
            ],
            manual_import_date=self.day,
        )

    def test_totals(self):
        self.assertEqual(
            self.helpers.get_totals(),
            {"total_count": 3, "mac_count": 2, "ssid_count": 2},
        )

    def test_daily_stats_per_device(self):
        rows = {
            (row.date, row.device): (row.ssid, row.mac, row.probe_request)
            for row in self.helpers.get_all_data_from_daily_captured_stats_per_device()
        }

        self.assertEqual(
            rows,
            {(self.day, "RPI-1"): (1, 2, 2), (self.day, "RPI-2"): (1, 1, 1)},
        )

    def test_daily_stats_by_date(self):
        helpers = self.helpers

        self.assertEqual(
            len(
                helpers.get_today_data_from_daily_captured_stats_per_device(
                    import_date=self.day
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                helpers.get_data_from_daily_captured_stats_per_device_between_dates(
                    self.day, self.day
                )
            ),
            2,
        )
        self.assertEqual(
            helpers.get_data_from_daily_captured_stats_per_device_between_dates(
                self.day + timedelta(days=1), self.today()
            ),
            [],
        )

    def test_country_by_alpha2(self):
        self.add(
            self.models.Country(
                name="France", alpha2="FR", alpha3="FRA", country_code="250"
            )
        )

        self.assertEqual(self.helpers.get_country_id_with_alpha2("FR").name, "France")
        self.assertIsNone(self.helpers.get_country_id_with_alpha2("XX"))

    def test_deprecated_view_queries(self):
        helpers = self.helpers

        with self.assertWarns(DeprecationWarning):
            devices = helpers.get_all_data_from_location_mapping_resolved()
        with self.assertWarns(DeprecationWarning):
            totals = helpers.get_device_total_captured_data(Device.RPI_1)
        with self.assertWarns(DeprecationWarning):
            helpers.get_all_data_from_company_capture_summary()
        with self.assertWarns(DeprecationWarning):
            helpers.get_all_data_from_company_capture_summary_by_device(Device.RPI_1)

        self.assertEqual(
            {device.device for device in devices}, {device.value for device in Device}
        )
        self.assertEqual((totals.ssid, totals.mac, totals.probe_request), (1, 2, 2))


if __name__ == "__main__":
    unittest.main()
