import unittest

from aggregator.core.orm.models import MAC


class TestMACValidator(unittest.TestCase):

    def test_mac_sets_uaa_flag(self):
        cases = [
            # (mac, expected_uaa)
            ("00:00:00:00:00:00", True),  # universal
            ("02:00:00:00:00:00", False),  # locally administered
            ("AA:BB:CC:DD:EE:FF", False),
            ("AE:BB:CC:DD:EE:FF", False),
            ("06:11:22:33:44:55", False),
        ]
        for mac_value, expected in cases:
            with self.subTest(mac=mac_value):
                mac = MAC(mac=mac_value)
                self.assertEqual(mac.uaa, expected)


if __name__ == "__main__":
    unittest.main()
