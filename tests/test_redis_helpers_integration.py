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


if __name__ == "__main__":
    unittest.main()
