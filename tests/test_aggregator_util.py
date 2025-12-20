import unittest

from aggregator.util import clean_string, extract_device_name


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


if __name__ == "__main__":
    unittest.main()
