import unittest

from aggregator.core.orm.models import IEEERegistry
from aggregator.util.util import (
    clean_string,
    extract_device_name,
    mac_normalize,
    mac_to_oui_candidates,
)


class TestUtils(unittest.TestCase):

    def test_extract_device_name(self):
        self.assertEqual(extract_device_name("RPI-1-2025-10-31"), "RPI-1")
        self.assertEqual(extract_device_name("RPI-2-2025-12-15"), "RPI-2")

        with self.assertRaises(AttributeError):
            self.assertEqual(extract_device_name("RPI-1"), "RPI-1")

        with self.assertRaises(AttributeError):
            extract_device_name("RPI-1-2025-10-31-invalid")

        with self.assertRaises(AttributeError):
            extract_device_name("RPI-1-20251031")

        with self.assertRaises(AttributeError):
            extract_device_name("")

    def test_clean_string(self):
        self.assertEqual(clean_string("hello\x00world"), "helloworld")
        self.assertEqual(clean_string("test\x1fvalue"), "testvalue")
        self.assertEqual(clean_string("good\x7fbye"), "goodbye")

        self.assertEqual(clean_string("你好"), "你好")
        self.assertEqual(clean_string("\x00hello\x7f"), "hello")
        self.assertEqual(clean_string("\x00\x01\x02"), "")
        self.assertEqual(clean_string(""), "")
        self.assertNotEqual(clean_string("SSID "), "SSID")
        self.assertEqual(clean_string(" SSID "), " SSID ")


class TestMacUtils(unittest.TestCase):

    def test_mac_normalize(self):
        test_cases = [
            {"input": "aa:bb:cc:dd:ee:ff", "expected": "AABBCCDDEEFF"},
            {"input": "AABBCCDDEEFF", "expected": "AABBCCDDEEFF"},
            {"input": "Aa:Bb:Cc:Dd:Ee:Ff", "expected": "AABBCCDDEEFF"},
            {"input": "", "expected": ""},
        ]

        for case in test_cases:
            with self.subTest(mac=case["input"]):
                self.assertEqual(mac_normalize(case["input"]), case["expected"])

    def test_mac_to_oui_candidates(self):
        test_cases = [
            {
                "input": "aa:bb:cc:dd:ee:ff",
                "expected": {
                    IEEERegistry.MA_L: "AABBCC",
                    IEEERegistry.MA_M: "AABBCCD",
                    IEEERegistry.MA_S: "AABBCCDDE",
                },
            },
            {
                "input": "AABBCCDDEEFF",
                "expected": {
                    IEEERegistry.MA_L: "AABBCC",
                    IEEERegistry.MA_M: "AABBCCD",
                    IEEERegistry.MA_S: "AABBCCDDE",
                },
            },
            {
                "input": "aa:bb:cc",
                "expected": {
                    IEEERegistry.MA_L: "AABBCC",
                    IEEERegistry.MA_M: "AABBCC",
                    IEEERegistry.MA_S: "AABBCC",
                },
            },
        ]

        for case in test_cases:
            with self.subTest(mac=case["input"]):
                result = mac_to_oui_candidates(case["input"])
                self.assertEqual(result, case["expected"])


if __name__ == "__main__":
    unittest.main()
