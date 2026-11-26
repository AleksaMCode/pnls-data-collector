"""End-to-end tests of the stats API: Supabase, the Redis cache and Firebase authentication."""

import base64
import json
import secrets
import time
import unittest
import uuid
from unittest import mock

from fastapi.testclient import TestClient
from fastapi_cache import FastAPICache

from tests.integration.containers import (
    FIREBASE_TEST_PROJECT_ID,
    REDIS_DB_STATS_API_CACHE,
    connect_firebase_emulator,
    create_firebase_test_user,
    redis_client,
    redis_url,
    requires_firebase,
    requires_postgres,
    requires_redis,
)
from tests.integration.stats_api_db import StatsApiDatabaseMixin
from tests.support.fake_http import unused_port
from tests.support.stats_api_loader import TEST_CACHE_TTL_SECONDS, build_app

TOTAL = {"macCount": 9, "ssidCount": 5, "probeRequestCount": 1159}
CACHED_ROUTES = (
    "/stats/total",
    "/stats/average/daily-counts",
    "/stats/last-30-days",
    "/stats/last-30-days/totals-with-series",
    "/stats/previous-30-days/totals",
    "/stats/probe-requests-per-device",
    "/stats/monthly-totals",
    "/stats/series",
    "/stats/series/RPI-2",
    "/stats/devices",
    "/stats/manufacturers",
    "/stats/sankey",
)
# Changes something that every cached route reads, so a database read gives a new answer.
CHANGE_EVERY_TABLE = (
    "UPDATE daily_imports_probes SET count = count + 1",
    "UPDATE daily_imports_mac SET count = count + 1",
    "UPDATE daily_imports_ssid SET count = count + 1",
    "UPDATE device_daily_imports SET probes = probes + 1, mac = mac + 1, ssid = ssid + 1",
    "UPDATE devices SET location = location || ' (moved)'",
    "UPDATE manufacturer_stats SET total_occurrences = total_occurrences + 1",
    "UPDATE device_manufacturer_stats SET manufacturer_data = "
    '\'[{"company": "Initech", "country": "France"}]\'',
    "UPDATE unique_total_stats SET totals = jsonb_set(totals::jsonb, '{macCount}', '1')",
)


def unsigned_token(**claims) -> str:
    """An ID token the Authentication emulator would accept, unless its claims are wrong."""

    def part(value: dict) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()
        )

    now = int(time.time())
    payload = {
        "iss": f"https://securetoken.google.com/{FIREBASE_TEST_PROJECT_ID}",
        "aud": FIREBASE_TEST_PROJECT_ID,
        "sub": "user-1",
        "user_id": "user-1",
        "auth_time": now - 60,
        "iat": now - 60,
        "exp": now + 3600,
        **claims,
    }
    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(payload)}."


@requires_postgres
class ApiTestCase(StatsApiDatabaseMixin, unittest.TestCase):
    """Runs the app with its lifespan (Redis cache, Firebase setup), as `uvicorn` would."""

    server_env = "dev"
    redis_connection: str

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.enterClassContext(
            mock.patch.dict("os.environ", {"REDIS_CONNECTION": cls.redis_connection})
        )
        cls.main = build_app({"SERVER_ENV": cls.server_env})
        cls.prepare_app()
        # FastAPICache.init() is a no-op once the cache is set up, so without a reset the lifespan
        # would keep the backend (and Redis) of whichever app ran first in this process.
        FastAPICache.reset()
        cls.addClassCleanup(FastAPICache.reset)
        cls.client = cls.enterClassContext(
            TestClient(cls.main.app, raise_server_exceptions=False)
        )

    @classmethod
    def prepare_app(cls):
        # No Firebase project in dev: authentication is off, its setup is not needed.
        cls.enterClassContext(mock.patch.object(cls.main, "setup_firebase_auth"))


@requires_redis
class TestRedisCache(ApiTestCase):
    database_prefix = "stats_api_cache"

    @classmethod
    def setUpClass(cls):
        cls.redis_connection = redis_url(REDIS_DB_STATS_API_CACHE)
        super().setUpClass()
        cls.cache = redis_client(REDIS_DB_STATS_API_CACHE)

    def setUp(self):
        super().setUp()
        self.cache.flushdb()

    def test_response_is_cached_in_redis(self):
        first = self.client.get("/stats/total")
        self.execute("UPDATE daily_imports_probes SET count = count + 1")

        second = self.client.get("/stats/total")

        self.assertEqual(first.json(), TOTAL)
        self.assertEqual(second.json(), TOTAL)
        self.assertTrue(
            any(key.startswith("stats-api-cache:") for key in self.cache.keys("*"))
        )

    def test_no_cache_header_reads_the_database(self):
        self.client.get("/stats/total")
        self.execute("UPDATE daily_imports_probes SET count = count + 1")

        response = self.client.get(
            "/stats/total", headers={"Cache-Control": "no-cache"}
        )

        self.assertEqual(
            response.json()["probeRequestCount"], TOTAL["probeRequestCount"] + 5
        )

    def test_cached_entries_expire(self):
        self.client.get("/stats/total")

        # fastapi-cache hashes the request into the key, after the service's prefix.
        (key,) = self.cache.keys("stats-api-cache:*")
        # REDIS_TTL, a few seconds less for the time the test took.
        self.assertGreaterEqual(self.cache.ttl(key), TEST_CACHE_TTL_SECONDS - 10)
        self.assertLessEqual(self.cache.ttl(key), TEST_CACHE_TTL_SECONDS)

    def test_every_cached_route_answers_the_same_from_redis(self):
        for path in CACHED_ROUTES:
            with self.subTest(path=path):
                self.cache.flushdb()
                self.reseed()
                miss = self.client.get(path)
                for sql in CHANGE_EVERY_TABLE:
                    self.execute(sql)

                hit = self.client.get(path)
                fresh = self.client.get(path, headers={"Cache-Control": "no-cache"})

                self.assertEqual(miss.status_code, 200)
                # Byte for byte: the JSON round trip through Redis changed nothing.
                self.assertEqual(hit.content, miss.content)
                # And the hit really came from the cache: the database now answers otherwise.
                self.assertNotEqual(fresh.content, miss.content)

    def test_parameters_get_their_own_cache_entries(self):
        for first, second in (
            (
                "/stats/probe-requests-per-device?n_days=1",
                "/stats/probe-requests-per-device?n_days=30",
            ),
            ("/stats/series/RPI-1", "/stats/series/RPI-2"),
        ):
            with self.subTest(first=first, second=second):
                self.cache.flushdb()
                first_response = self.client.get(first)
                second_response = self.client.get(second)

                self.assertEqual(len(self.cache.keys("stats-api-cache:*")), 2)
                self.assertNotEqual(first_response.content, second_response.content)
                self.assertEqual(self.client.get(first).content, first_response.content)

    def test_ssid_list_is_always_read_from_the_database(self):
        self.client.get("/stats/ssids")
        self.execute("DELETE FROM ssid_stats WHERE ssid = 'CERN'")

        response = self.client.get("/stats/ssids")

        self.assertEqual(response.json()["pagination"]["total"], 4)

    def test_csv_export_through_the_api(self):
        response = self.client.get(
            "/stats/ssids/export", params={"sort_by": "first_seen", "sort_order": "asc"}
        )

        lines = response.text.strip().splitlines()
        self.assertEqual(lines[0], "ssid,seen_count,first_seen,last_seen")
        self.assertEqual(lines[1], "CERN,5,2026-06-01 08:00:00,2026-06-14 09:00:00")
        self.assertEqual(len(lines), 6)


class TestUnreachableRedis(ApiTestCase):
    database_prefix = "stats_api_no_redis"
    # Nothing listens there: every cache read and write fails at once.
    redis_connection = f"redis://127.0.0.1:{unused_port()}/0"

    def test_cached_routes_are_served_from_the_database(self):
        with self.assertLogs("fastapi_cache.decorator", "WARNING") as logs:
            response = self.client.get("/stats/total")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), TOTAL)
        # The cache was really tried, and failed, on the dead port.
        self.assertIn("Error retrieving cache key", logs.output[0])


@requires_redis
@requires_firebase
class TestFirebaseAuthentication(ApiTestCase):
    """The production setup, with ID tokens issued by the Firebase Authentication emulator.

    With an emulator, the Admin SDK checks a token's project but neither its signature nor its
    expiry, so expired and forged tokens are only covered by the unit tests of the middleware.
    """

    database_prefix = "stats_api_auth"
    server_env = "production"

    @classmethod
    def setUpClass(cls):
        cls.redis_connection = redis_url(REDIS_DB_STATS_API_CACHE)
        super().setUpClass()
        email = f"stats-api-{uuid.uuid4().hex[:8]}@example.com"
        cls.token = create_firebase_test_user(email, secrets.token_urlsafe(16))

    @classmethod
    def prepare_app(cls):
        # The default Firebase app points at the emulators, so setup_firebase_auth() keeps it.
        connect_firebase_emulator()

    def setUp(self):
        super().setUp()
        redis_client(REDIS_DB_STATS_API_CACHE).flushdb()

    def get(self, token: str | None = None, path: str = "/stats/total"):
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        return self.client.get(path, headers=headers)

    def test_signed_in_user_gets_the_stats(self):
        response = self.get(self.token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), TOTAL)

    def test_request_without_a_token_is_refused(self):
        self.assertEqual(self.get().status_code, 401)

    def test_garbage_token_is_refused(self):
        self.assertEqual(self.get("not-a-token").status_code, 401)

    def test_token_of_another_project_is_refused(self):
        token = unsigned_token(
            iss="https://securetoken.google.com/demo-other", aud="demo-other"
        )

        self.assertEqual(self.get(token).status_code, 401)

    def test_well_formed_token_of_this_project_is_accepted(self):
        # The claims of a real emulator token: shows the other-project test fails on its claims.
        self.assertEqual(self.get(unsigned_token()).status_code, 200)

    def test_health_and_docs_without_a_token(self):
        self.assertEqual(self.get(path="/health").status_code, 200)
        self.assertEqual(self.get(self.token, path="/docs").status_code, 404)


if __name__ == "__main__":
    unittest.main()
