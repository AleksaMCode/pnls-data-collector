"""Unit tests for the stats API's Firebase authentication and its production and dev setups."""

import json
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from tests.support.stats_api_loader import build_app, load_app_modules

modules = load_app_modules()
auth = modules["middleware.auth"]
routes = modules["routers.stats"]
redis_helpers = modules["core.redis.helpers"]

USER = {"uid": "user-1", "email": "user@example.com"}


class AppTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        InMemoryBackend._store.clear()
        # FastAPICache.init() is a no-op once the cache is set up, so it is reset first.
        FastAPICache.reset()
        FastAPICache.init(InMemoryBackend(), prefix="test")
        self.addCleanup(FastAPICache.reset)
        patcher = mock.patch.object(
            routes, "fetch_total_stats", return_value={"total": 1}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def client_for(self, env: dict) -> TestClient:
        return TestClient(build_app(env).app)


class TestFirebaseAuthMiddleware(AppTestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_for({"SERVER_ENV": "production"})
        patcher = mock.patch.object(auth.auth, "verify_id_token")
        self.verify = patcher.start()
        self.addCleanup(patcher.stop)
        self.verify.return_value = USER

    def get(self, path="/stats/total", **headers):
        return self.client.get(path, headers=headers)

    def test_valid_token_is_let_through(self):
        response = self.get(Authorization="Bearer good-token")

        self.assertEqual(response.status_code, 200)
        self.verify.assert_called_once_with("good-token")

    def test_signed_in_user_is_kept_on_the_request(self):
        seen = {}
        app = build_app({"SERVER_ENV": "production"}).app

        @app.get("/whoami")
        async def whoami(request: auth.Request):
            seen.update(request.state.firebase_user)
            return {}

        TestClient(app).get("/whoami", headers={"Authorization": "Bearer good-token"})

        self.assertEqual(seen, USER)

    def test_missing_or_malformed_header_is_refused(self):
        for headers in (
            {},
            {"Authorization": "Basic dXNlcjpwYXNz"},
            {"Authorization": "bearer x"},
        ):
            with self.subTest(headers=headers):
                response = self.get(**headers)

                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.json(),
                    {"detail": "Missing or invalid Authorization header."},
                )
        self.verify.assert_not_called()

    def test_empty_token_is_refused(self):
        response = self.get(Authorization="Bearer    ")

        self.assertEqual(response.json(), {"detail": "Empty Bearer token."})

    def test_invalid_token_is_refused(self):
        self.verify.side_effect = ValueError("Token expired")

        response = self.get(Authorization="Bearer old-token")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(), {"detail": "Invalid or expired Firebase token."}
        )

    def test_health_needs_no_token(self):
        self.assertEqual(self.get("/health").status_code, 200)

    def test_preflight_needs_no_token(self):
        response = self.client.options(
            "/stats/total",
            headers={
                "Origin": "https://dashboard.example",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.verify.assert_not_called()


class TestSetupFirebaseAuth(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(auth.firebase_admin, "_apps", {})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.initialize = self.enterContext(
            mock.patch.object(auth.firebase_admin, "initialize_app")
        )
        self.certificate = self.enterContext(
            mock.patch.object(auth.credentials, "Certificate")
        )

    def test_credentials_are_read_from_the_environment(self):
        service_account = {"type": "service_account", "project_id": "pnls"}

        with mock.patch.dict(
            "os.environ", {"FIREBASE_CREDENTIALS_JSON": json.dumps(service_account)}
        ):
            auth.setup_firebase_auth()

        self.certificate.assert_called_once_with(service_account)
        self.initialize.assert_called_once_with(self.certificate.return_value)

    def test_missing_credentials_stop_the_start(self):
        with mock.patch.dict("os.environ", {"FIREBASE_CREDENTIALS_JSON": ""}):
            with self.assertRaisesRegex(RuntimeError, "is required"):
                auth.setup_firebase_auth()

    def test_invalid_json_stops_the_start(self):
        with mock.patch.dict("os.environ", {"FIREBASE_CREDENTIALS_JSON": "{not json"}):
            with self.assertRaisesRegex(RuntimeError, "not valid JSON"):
                auth.setup_firebase_auth()

    def test_existing_app_is_kept(self):
        with mock.patch.object(auth.firebase_admin, "_apps", {"[DEFAULT]": object()}):
            auth.setup_firebase_auth()

        self.initialize.assert_not_called()


class TestAppSetup(AppTestCase):
    def test_production_hides_the_docs_and_requires_a_token(self):
        client = self.client_for({"SERVER_ENV": "production"})

        for path in ("/docs", "/redoc", "/openapi.json"):
            with self.subTest(path=path):
                self.assertEqual(
                    client.get(path, headers={"Authorization": "Bearer x"}).status_code,
                    404,
                )
        self.assertEqual(client.get("/stats/total").status_code, 401)

    def test_dev_shows_the_docs_and_needs_no_token(self):
        client = self.client_for({"SERVER_ENV": "dev"})

        self.assertEqual(client.get("/docs").status_code, 200)
        self.assertEqual(client.get("/stats/total").json(), {"total": 1})

    def test_production_only_allows_the_configured_origins(self):
        client = self.client_for(
            {"SERVER_ENV": "production", "ALLOWED_ORIGINS": "https://dashboard.example"}
        )

        def preflight(origin):
            return client.options(
                "/stats/total",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )

        self.assertEqual(
            preflight("https://dashboard.example").headers[
                "access-control-allow-origin"
            ],
            "https://dashboard.example",
        )
        self.assertNotIn(
            "access-control-allow-origin", preflight("https://evil.example").headers
        )

    @unittest.expectedFailure
    def test_without_a_server_env_a_token_is_required(self):
        """Known bug: any SERVER_ENV other than exactly "production" (here: none) turns the
        authentication off. Remove the decorator once the setup fails closed.
        """
        client = self.client_for({})

        self.assertEqual(client.get("/stats/total").status_code, 401)

    @unittest.expectedFailure
    def test_spaces_around_allowed_origins_are_ignored(self):
        """Known issue: ALLOWED_ORIGINS is split on commas without stripping, so only the first
        origin of "a, b" is allowed. Remove the decorator once the values are stripped.
        """
        client = self.client_for(
            {
                "SERVER_ENV": "production",
                "ALLOWED_ORIGINS": "https://a.example, https://b.example",
            }
        )

        response = client.options(
            "/stats/total",
            headers={
                "Origin": "https://b.example",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(
            response.headers.get("access-control-allow-origin"), "https://b.example"
        )


class TestInitRedisCache(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.redis = self.enterContext(mock.patch.object(redis_helpers, "Redis"))
        self.cache_init = self.enterContext(
            mock.patch.object(redis_helpers.FastAPICache, "init")
        )
        self.enterContext(mock.patch.object(redis_helpers.logfire, "instrument_redis"))

    async def test_connection_url_wins(self):
        with mock.patch.dict(
            "os.environ", {"REDIS_CONNECTION": "redis://cache:6379/2"}
        ):
            client = await redis_helpers.init_redis_cache()

        self.redis.from_url.assert_called_once_with("redis://cache:6379/2")
        self.assertIs(client, self.redis.from_url.return_value)

    async def test_host_and_port_otherwise(self):
        env = {
            "REDIS_CONNECTION": "",
            "REDIS_URL": "cache",
            "REDIS_PORT": "6380",
            "REDIS_USERNAME": "stats",
            "REDIS_PASSWORD": "secret",
        }
        with mock.patch.dict("os.environ", env):
            await redis_helpers.init_redis_cache()

        self.redis.assert_called_once_with(
            host="cache",
            port=6380,
            username="stats",
            password="secret",
            decode_responses=False,
        )

    async def test_cache_uses_the_service_prefix(self):
        with mock.patch.dict(
            "os.environ", {"REDIS_CONNECTION": "redis://cache:6379/2"}
        ):
            await redis_helpers.init_redis_cache()

        self.assertEqual(
            self.cache_init.call_args.kwargs, {"prefix": "stats-api-cache"}
        )

    @unittest.expectedFailure
    async def test_client_has_timeouts(self):
        """Known issue: without socket timeouts, a Redis host that stops answering makes every
        cached request wait for the OS TCP timeout. Remove the decorator once they are set.
        """
        env = {"REDIS_CONNECTION": "", "REDIS_URL": "cache", "REDIS_PORT": "6379"}
        with mock.patch.dict("os.environ", env):
            await redis_helpers.init_redis_cache()

        self.assertIn("socket_connect_timeout", self.redis.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
