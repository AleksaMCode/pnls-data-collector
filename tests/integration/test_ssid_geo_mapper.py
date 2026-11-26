"""Integration and end-to-end tests of the SSID GEO mapper on Postgres with the aggregator schema."""

import json
import os
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from urllib.parse import parse_qs, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from tests.integration.containers import create_aggregator_database, requires_postgres
from tests.support.aggregator_loader import no_retry_wait
from tests.support.fake_http import FakeMattermost, start_in_background, unused_port
from tests.support.ssid_geo_loader import import_ssid_geo_module

helpers = import_ssid_geo_module("ssid_geo_mapper.core.orm.helpers")
main = import_ssid_geo_module("ssid_geo_mapper.main")
wigle_module = import_ssid_geo_module("ssid_geo_mapper.wigle_adapter.wigle")
mattermost = import_ssid_geo_module("util.mattermost.helpers")

COUNTRIES = (
    ("Switzerland", "CH", "CHE", "756"),
    ("France", "FR", "FRA", "250"),
)
GENEVA = {"ssid": "home", "lat": 46.20, "long": 6.14, "alpha2": "CH"}
MEYRIN = {"ssid": "home", "lat": 46.23, "long": 6.07, "alpha2": "ch"}
PARIS = {"ssid": "home", "lat": 48.85, "long": 2.35, "alpha2": "FR"}


@requires_postgres
class SsidGeoDatabaseTestCase(unittest.TestCase):
    """Gives a test class its own database with the aggregator schema, which owns these tables."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = create_engine(create_aggregator_database("ssid_geo"))
        cls.addClassCleanup(cls.engine.dispose)
        session = sessionmaker(bind=cls.engine, expire_on_commit=False)
        patcher = mock.patch.object(helpers, "_session", session)
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def setUp(self):
        super().setUp()
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE ssid, ssid_geo, ssid_geo_reduced, country "
                    "RESTART IDENTITY CASCADE"
                )
            )
            for name, alpha2, alpha3, code in COUNTRIES:
                connection.execute(
                    text(
                        "INSERT INTO country (name, alpha2, alpha3, country_code) "
                        "VALUES (:name, :alpha2, :alpha3, :code)"
                    ),
                    {"name": name, "alpha2": alpha2, "alpha3": alpha3, "code": code},
                )

    def add_ssid(self, ssid: str, **columns) -> int:
        values = {"ssid": ssid, "mapped": False, "has_geo": False, **columns}
        names = ", ".join(values)
        params = ", ".join(f":{name}" for name in values)
        with self.engine.begin() as connection:
            return connection.execute(
                text(f"INSERT INTO ssid ({names}) VALUES ({params}) RETURNING id"),
                values,
            ).scalar()

    def rows(self, sql: str, **params) -> list[tuple]:
        with self.engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(sql), params)]

    def ssid_row(self, ssid_id: int) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT mapped, has_geo, failed_attempts, last_failure_reason, "
                    "last_attempt_at IS NOT NULL AS attempted FROM ssid WHERE id = :id"
                ),
                {"id": ssid_id},
            )
            return dict(row.mappings().one())


class TestGetUnmappedSsids(SsidGeoDatabaseTestCase):
    def test_never_failed_first_then_fewest_failures_then_least_recently_tried(self):
        self.add_ssid("failed-twice", failed_attempts=2, last_attempt_at="2026-06-01")
        self.add_ssid(
            "failed-once-recently", failed_attempts=1, last_attempt_at="2026-06-10"
        )
        self.add_ssid("fresh-1")
        self.add_ssid(
            "failed-once-long-ago", failed_attempts=1, last_attempt_at="2026-05-01"
        )
        self.add_ssid("fresh-2")

        queue = [ssid.ssid for ssid in helpers.get_unmapped_ssids(10)]

        self.assertEqual(
            queue,
            [
                "fresh-1",
                "fresh-2",
                "failed-once-long-ago",
                "failed-once-recently",
                "failed-twice",
            ],
        )

    def test_mapped_located_and_wildcard_ssids_are_left_out(self):
        self.add_ssid("*")
        self.add_ssid("mapped", mapped=True)
        self.add_ssid("located", has_geo=True)
        self.add_ssid("pending")

        self.assertEqual(
            [ssid.ssid for ssid in helpers.get_unmapped_ssids(10)], ["pending"]
        )

    def test_limit(self):
        for index in range(5):
            self.add_ssid(f"ssid-{index}")

        self.assertEqual(len(helpers.get_unmapped_ssids(3)), 3)

    def test_ssids_can_be_read_after_the_session_closed(self):
        self.add_ssid("pending", failed_attempts=1)

        (ssid,) = helpers.get_unmapped_ssids(1)

        self.assertEqual((ssid.ssid, ssid.failed_attempts), ("pending", 1))

    def test_database_error_is_retried_then_raised(self):
        from tenacity import RetryError

        failing = mock.Mock(side_effect=RuntimeError("database is down"))
        with (
            mock.patch.object(helpers, "_session", failing),
            no_retry_wait(helpers.get_unmapped_ssids),
            self.assertRaises(RetryError),
        ):
            helpers.get_unmapped_ssids(1)

        self.assertEqual(failing.call_count, 10)


class TestInsertSsidGeoBatch(SsidGeoDatabaseTestCase):
    def test_locations_are_stored_with_their_country(self):
        ssid_id = self.add_ssid("home")

        helpers.insert_ssid_geo_batch(ssid_id, [GENEVA, MEYRIN, PARIS], [GENEVA, PARIS])

        self.assertEqual(
            self.rows(
                "SELECT g.latitude, g.longitude, c.alpha2 FROM ssid_geo g "
                "LEFT JOIN country c ON c.id = g.country ORDER BY g.id"
            ),
            [(46.20, 6.14, "CH"), (46.23, 6.07, "CH"), (48.85, 2.35, "FR")],
        )
        self.assertEqual(
            self.rows(
                "SELECT g.latitude, c.alpha2 FROM ssid_geo_reduced g "
                "LEFT JOIN country c ON c.id = g.country ORDER BY g.id"
            ),
            [(46.20, "CH"), (48.85, "FR")],
        )

    def test_unknown_or_missing_country_is_stored_as_null(self):
        ssid_id = self.add_ssid("home")

        helpers.insert_ssid_geo_batch(
            ssid_id,
            [{**GENEVA, "alpha2": "ZZ"}, {**PARIS, "alpha2": None}],
            [],
        )

        self.assertEqual(self.rows("SELECT country FROM ssid_geo"), [(None,), (None,)])

    def test_ssid_is_marked_mapped_with_locations(self):
        ssid_id = self.add_ssid("home")

        helpers.insert_ssid_geo_batch(ssid_id, [GENEVA], [GENEVA])

        row = self.ssid_row(ssid_id)
        self.assertEqual(
            (row["mapped"], row["has_geo"], row["attempted"]), (True, True, True)
        )

    def test_rows_get_todays_date(self):
        ssid_id = self.add_ssid("home")

        helpers.insert_ssid_geo_batch(ssid_id, [GENEVA], [GENEVA])

        self.assertEqual(
            self.rows("SELECT created_date = CURRENT_DATE FROM ssid_geo"), [(True,)]
        )

    def test_failed_insert_leaves_nothing_behind(self):
        # No SSID with this id: the foreign key rejects the rows.
        with self.assertRaises(IntegrityError):
            helpers.insert_ssid_geo_batch(999, [GENEVA], [GENEVA])

        self.assertEqual(self.rows("SELECT count(*) FROM ssid_geo"), [(0,)])
        self.assertEqual(self.rows("SELECT count(*) FROM ssid_geo_reduced"), [(0,)])

    def test_resolved_views_show_the_reduced_locations(self):
        home = self.add_ssid("home")
        cafe = self.add_ssid("cafe")
        helpers.insert_ssid_geo_batch(home, [GENEVA, PARIS], [GENEVA, PARIS])
        helpers.insert_ssid_geo_batch(cafe, [PARIS], [PARIS])

        self.assertEqual(
            self.rows(
                "SELECT ssid, country, country_alpha3 FROM ssid_geo_reduced_resolved"
            ),
            [
                ("home", "Switzerland", "CHE"),
                ("home", "France", "FRA"),
                ("cafe", "France", "FRA"),
            ],
        )
        # Only the SSIDs seen in a single place.
        self.assertEqual(
            self.rows("SELECT ssid FROM one_ssid_geo_reduced_resolved"), [("cafe",)]
        )


class TestSsidStatusUpdates(SsidGeoDatabaseTestCase):
    def test_ssid_without_locations_is_mapped_without_geo(self):
        ssid_id = self.add_ssid("cafe")

        helpers.update_ssid_mapped(ssid_id, has_geo=False)

        row = self.ssid_row(ssid_id)
        self.assertEqual(
            (row["mapped"], row["has_geo"], row["attempted"]), (True, False, True)
        )

    def test_failures_are_counted_and_the_ssid_stays_unmapped(self):
        ssid_id = self.add_ssid("broken")

        helpers.record_ssid_failure(ssid_id, "500")
        helpers.record_ssid_failure(ssid_id, "timeout")

        self.assertEqual(
            self.ssid_row(ssid_id),
            {
                "mapped": False,
                "has_geo": False,
                "failed_attempts": 2,
                "last_failure_reason": "timeout",
                "attempted": True,
            },
        )

    def test_failure_reason_is_cut_to_the_column_length(self):
        ssid_id = self.add_ssid("broken")

        helpers.record_ssid_failure(ssid_id, "x" * 100)

        self.assertEqual(self.ssid_row(ssid_id)["last_failure_reason"], "x" * 64)


class FakeWigle(ThreadingHTTPServer):
    """Answers WiGLE network searches from `answers`: ssid -> (status, payload, headers)."""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _FakeWigleHandler)
        self.answers = {}
        self.searched = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/api/v2/network/search"


class _FakeWigleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        (ssid,) = parse_qs(urlparse(self.path).query)["ssid"]
        self.server.searched.append(ssid)
        status, payload, headers = self.server.answers.get(
            ssid, (200, {"success": True, "results": []}, {})
        )
        body = json.dumps(payload).encode()
        self.send_response(status)
        for name, value in {"Content-Type": "application/json", **headers}.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def wigle_results(*locations) -> tuple:
    return (
        200,
        {
            "success": True,
            "results": [
                {
                    "ssid": loc["ssid"],
                    "trilat": loc["lat"],
                    "trilong": loc["long"],
                    "country": loc["alpha2"],
                }
                for loc in locations
            ],
        },
        {},
    )


class TestMappingEndToEnd(SsidGeoDatabaseTestCase):
    """POST /ssid_mapping with the real WiGLE client against a fake server, on the test database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import requests
        from fastapi.testclient import TestClient

        cls.requests = requests
        cls.wigle = FakeWigle()
        start_in_background(cls.wigle, cls)
        cls.mattermost = FakeMattermost()
        start_in_background(cls.mattermost, cls)
        cls.client = cls.enterClassContext(
            TestClient(main.app, raise_server_exceptions=False)
        )

    def setUp(self):
        super().setUp()
        self.wigle.answers = {}
        self.wigle.searched.clear()
        self.mattermost.messages.clear()
        self.point_wigle_at(self.wigle.url)
        for name, value in (
            ("SLACK_WEBHOOK_URL", self.mattermost.url),
            ("WIGLE_BASE_DELAY_SECONDS", 0.0),
            ("WIGLE_DELAY_JITTER_SECONDS", 0.0),
        ):
            self.patch(main, name, value)
        # Under ENV=test, util.mattermost.helpers does not import requests.
        patcher = mock.patch.object(mattermost, "requests", self.requests, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.dict(
            os.environ, {"WIGLE_API_KEY": "test-key", "WIGLE_API_SECRET": "test-secret"}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def point_wigle_at(self, url: str):
        self.patch(wigle_module.Wigle, "URL", url)

    def summary(self) -> str:
        return self.mattermost.messages[-1]["text"]

    def test_locations_no_results_and_failures_are_stored(self):
        home = self.add_ssid("home")
        cafe = self.add_ssid("cafe")
        broken = self.add_ssid("broken")
        self.wigle.answers = {
            "home": wigle_results(GENEVA, MEYRIN, PARIS),
            "broken": (500, {"message": "Internal error"}, {}),
        }

        response = self.client.post("/ssid_mapping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wigle.searched, ["home", "cafe", "broken"])
        self.assertEqual(
            self.rows("SELECT count(*) FROM ssid_geo WHERE ssid = :id", id=home), [(3,)]
        )
        # Meyrin is ~6 km from Geneva, within the 27 km reduction threshold.
        self.assertEqual(
            self.rows("SELECT country FROM ssid_geo_reduced_resolved"),
            [("Switzerland",), ("France",)],
        )
        self.assertEqual(
            (self.ssid_row(home)["mapped"], self.ssid_row(home)["has_geo"]),
            (True, True),
        )
        self.assertEqual(
            (self.ssid_row(cafe)["mapped"], self.ssid_row(cafe)["has_geo"]),
            (True, False),
        )
        self.assertEqual(
            (
                self.ssid_row(broken)["failed_attempts"],
                self.ssid_row(broken)["last_failure_reason"],
            ),
            (1, "500"),
        )

    def test_start_and_summary_reach_mattermost(self):
        self.add_ssid("home")
        self.add_ssid("cafe")
        self.wigle.answers = {"home": wigle_results(GENEVA)}

        self.client.post("/ssid_mapping")

        self.assertEqual(
            [message["username"] for message in self.mattermost.messages],
            ["SSID GEO Mapper", "SSID GEO Mapper"],
        )
        self.assertEqual(
            self.mattermost.messages[0]["text"], "SSID GEO mapping workflow started."
        )
        self.assertIn("With locations: 1 | No results: 1 | Failed: 0", self.summary())

    def test_rate_limit_leaves_the_rest_of_the_batch_untouched(self):
        first = self.add_ssid("first")
        limited = self.add_ssid("limited")
        later = self.add_ssid("later")
        self.wigle.answers = {
            "first": wigle_results({**GENEVA, "ssid": "first"}),
            "limited": (
                429,
                {"message": "too many queries today"},
                {"Retry-After": "3600"},
            ),
        }

        self.client.post("/ssid_mapping")

        self.assertEqual(self.wigle.searched, ["first", "limited"])
        self.assertTrue(self.ssid_row(first)["mapped"])
        for ssid_id in (limited, later):
            with self.subTest(ssid_id=ssid_id):
                self.assertEqual(
                    self.ssid_row(ssid_id),
                    {
                        "mapped": False,
                        "has_geo": False,
                        "failed_attempts": 0,
                        "last_failure_reason": None,
                        "attempted": False,
                    },
                )
        self.assertIn("ABORTED", self.summary())
        self.assertIn("Retry-After: 3600", self.summary())

    @unittest.expectedFailure
    def test_unreachable_wigle_does_not_count_against_the_ssids(self):
        """Known bug: each connection error is recorded as a failure of the SSID. Remove the
        decorator once errors that are not about the SSID stop the run instead.
        """
        ssid_ids = [self.add_ssid(name) for name in ("a", "b", "c")]
        self.point_wigle_at(f"http://127.0.0.1:{unused_port()}/api/v2/network/search")

        self.client.post("/ssid_mapping")

        self.assertEqual(
            [self.ssid_row(ssid_id)["failed_attempts"] for ssid_id in ssid_ids],
            [0, 0, 0],
        )


if __name__ == "__main__":
    unittest.main()
