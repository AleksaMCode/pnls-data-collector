import unittest

from aggregator.core.redis.helpers import mac_cache_key, ssid_cache_key


class TestRedisHelpersUnit(unittest.TestCase):
    def test_ssid_cache_key_builds_expected_key(self):
        self.assertEqual(ssid_cache_key("OfficeWiFi"), "ssid:id:OfficeWiFi")

    def test_mac_cache_key_normalizes_to_lowercase(self):
        self.assertEqual(
            mac_cache_key("AA:BB:CC:DD:EE:FF"),
            "mac:id:aa:bb:cc:dd:ee:ff",
        )


if __name__ == "__main__":
    unittest.main()
