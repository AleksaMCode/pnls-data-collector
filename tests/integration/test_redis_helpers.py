import time
import unittest

from tests.integration.containers import (
    REDIS_DB_REDIS_HELPERS,
    redis_client,
    requires_redis,
)


@requires_redis
class TestRedisHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from aggregator.core.redis import helpers as redis_helpers

        cls._redis_helpers = redis_helpers
        cls._original_client = redis_helpers.client

        # Logical database 1 of the shared Redis container, flushed before every test.
        cls._test_client = redis_client(db=REDIS_DB_REDIS_HELPERS)

        # Route helper calls to integration-test Redis client.
        redis_helpers.client = cls._test_client

    @classmethod
    def tearDownClass(cls):
        cls._redis_helpers.client = cls._original_client
        cls._test_client.close()

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

    def test_mac_ids_are_found_whatever_the_letter_case(self):
        self._redis_helpers.set_cached_mac_id("AA:BB:CC:DD:EE:FF", 42)

        self.assertEqual(self._redis_helpers.get_cached_mac_id("aa:bb:cc:dd:ee:ff"), 42)
        self.assertEqual(self._test_client.get("mac:id:aa:bb:cc:dd:ee:ff"), "42")

    def test_ssid_ids_keep_their_letter_case(self):
        self._redis_helpers.set_cached_ssid_id("CERN", 1)

        self.assertEqual(self._redis_helpers.get_cached_ssid_id("CERN"), 1)
        self.assertIsNone(self._redis_helpers.get_cached_ssid_id("cern"))

    def test_value_can_be_overwritten(self):
        self._redis_helpers.set_key_value("workflow:3", "STARTED", ttl=60)
        self._redis_helpers.set_key_value("workflow:3", "COMPLETED")

        self.assertEqual(self._redis_helpers.get_key_value("workflow:3"), "COMPLETED")
        self.assertEqual(self._test_client.ttl("workflow:3"), -1)

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
