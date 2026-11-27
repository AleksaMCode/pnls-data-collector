import unittest
from unittest import mock

from aggregator.core.redis import helpers
from aggregator.core.redis.helpers import mac_cache_key, ssid_cache_key


class TestRedisHelpers(unittest.TestCase):
    def test_ssid_cache_key_builds_expected_key(self):
        self.assertEqual(ssid_cache_key("OfficeWiFi"), "ssid:id:OfficeWiFi")

    def test_mac_cache_key_normalizes_to_lowercase(self):
        self.assertEqual(
            mac_cache_key("AA:BB:CC:DD:EE:FF"),
            "mac:id:aa:bb:cc:dd:ee:ff",
        )


class TestRedisUnavailable(unittest.TestCase):
    """A real Redis cannot be made to fail on demand, so the error paths use a failing client."""

    def setUp(self):
        failing_client = mock.MagicMock()
        failing_client.set.side_effect = ConnectionError("Redis down")
        failing_client.get.side_effect = ConnectionError("Redis down")
        patcher = mock.patch.object(helpers, "client", failing_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_set_returns_false(self):
        self.assertFalse(helpers.set_key_value("key", "value"))
        self.assertFalse(helpers.set_key_value("key", "value", ttl=10))

    def test_get_returns_none(self):
        self.assertIsNone(helpers.get_key_value("key"))

    def test_cache_lookups_fall_back_to_a_miss(self):
        # get_or_create_ssid_id / get_or_create_mac_id then read the database instead.
        self.assertIsNone(helpers.get_cached_ssid_id("CERN"))
        self.assertIsNone(helpers.get_cached_mac_id("AA:BB:CC:DD:EE:FF"))

    def test_cache_writes_report_failure(self):
        self.assertFalse(helpers.set_cached_ssid_id("CERN", 1))
        self.assertFalse(helpers.set_cached_mac_id("AA:BB:CC:DD:EE:FF", 2))


class TestRedisCommands(unittest.TestCase):
    """Checks the exact commands sent to Redis, including the cache TTL."""

    def setUp(self):
        self.client = mock.MagicMock()
        patcher = mock.patch.object(helpers, "client", self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_set_without_ttl_never_expires(self):
        helpers.set_key_value("key", "value")

        self.client.set.assert_called_once_with("key", "value")

    def test_cached_ids_expire_after_the_lookup_ttl(self):
        helpers.set_cached_ssid_id("CERN", 1)
        helpers.set_cached_mac_id("AA:BB:CC:DD:EE:FF", 2)

        self.assertEqual(
            self.client.set.call_args_list,
            [
                mock.call("ssid:id:CERN", "1", ex=helpers.LOOKUP_CACHE_TTL_SECONDS),
                mock.call(
                    "mac:id:aa:bb:cc:dd:ee:ff", "2", ex=helpers.LOOKUP_CACHE_TTL_SECONDS
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
