import time
import unittest

try:
    import redis
    from testcontainers.redis import RedisContainer
except ImportError:
    redis = None
    RedisContainer = None


@unittest.skipUnless(
    redis is not None and RedisContainer is not None,
    "redis and testcontainers are required for Redis integration tests",
)
class TestRedisHelpersIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from aggregator.core.redis import helpers as redis_helpers

        cls._redis_helpers = redis_helpers
        cls._original_client = redis_helpers.client

        cls._redis_container = RedisContainer("redis:8.8.0")
        cls._redis_container.start()

        host = cls._redis_container.get_container_host_ip()
        port = int(cls._redis_container.get_exposed_port(6379))

        cls._test_client = redis.Redis(
            host=host,
            port=port,
            db=1,
            decode_responses=True,
        )
        cls._test_client.ping()

        # Route helper calls to integration-test Redis client.
        redis_helpers.client = cls._test_client

    @classmethod
    def tearDownClass(cls):
        cls._redis_helpers.client = cls._original_client
        cls._redis_container.stop()

    def setUp(self):
        self._test_client.flushdb()

    def test_set_and_get_without_ttl(self):
        result = self._redis_helpers.set_key_value("workflow:1", "STARTED")
        self.assertTrue(result)
        self.assertEqual(self._redis_helpers.get_key_value("workflow:1"), "STARTED")
        self.assertEqual(self._test_client.ttl("workflow:1"), -1)

    def test_set_with_ttl(self):
        result = self._redis_helpers.set_key_value("workflow:2", "COMPLETED", ttl=1)
        self.assertTrue(result)
        self.assertEqual(self._redis_helpers.get_key_value("workflow:2"), "COMPLETED")
        time.sleep(1.2)
        self.assertIsNone(self._redis_helpers.get_key_value("workflow:2"))

    def test_get_missing_key_returns_none(self):
        self.assertIsNone(self._redis_helpers.get_key_value("missing"))

    def test_set_and_get_cached_ssid_id(self):
        result = self._redis_helpers.set_cached_ssid_id("MyWifi", 123)
        self.assertTrue(result)

        self.assertEqual(self._redis_helpers.get_cached_ssid_id("MyWifi"), 123)
        self.assertTrue(
            0
            < self._test_client.ttl(self._redis_helpers.ssid_cache_key("MyWifi"))
            <= 3600
        )

    def test_set_and_get_cached_mac_id(self):
        result = self._redis_helpers.set_cached_mac_id("AA:BB:CC:DD:EE:FF", 987)
        self.assertTrue(result)

        self.assertEqual(
            self._redis_helpers.get_cached_mac_id("AA:BB:CC:DD:EE:FF"),
            987,
        )
        self.assertTrue(
            0
            < self._test_client.ttl(
                self._redis_helpers.mac_cache_key("AA:BB:CC:DD:EE:FF")
            )
            <= 3600
        )

    def test_get_cached_ids_return_none_for_missing_keys(self):
        self.assertIsNone(self._redis_helpers.get_cached_ssid_id("missing-ssid"))
        self.assertIsNone(self._redis_helpers.get_cached_mac_id("missing-mac"))

    def test_get_cached_ids_return_none_for_non_integer_values(self):
        self._test_client.set(self._redis_helpers.ssid_cache_key("BadSSID"), "abc")
        self._test_client.set(
            self._redis_helpers.mac_cache_key("11:22:33:44:55:66"), "xyz"
        )

        self.assertIsNone(self._redis_helpers.get_cached_ssid_id("BadSSID"))
        self.assertIsNone(self._redis_helpers.get_cached_mac_id("11:22:33:44:55:66"))


if __name__ == "__main__":
    unittest.main()
