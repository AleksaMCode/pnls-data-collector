"""Unit tests for the shared util helpers: Firebase node keys, RSA key files and the Device enum."""

import tempfile
import unittest
from pathlib import Path

from tests.support.keys import test_rsa_key
from util.core.orm.models import Device
from util.util import (
    decrypt_data,
    encrypt_data,
    extract_device_name,
    load_rsa_key_from_file,
)


class TestExtractDeviceName(unittest.TestCase):
    def test_trailing_date_is_removed(self):
        self.assertEqual(extract_device_name("RPI-1-2025-10-31"), "RPI-1")

    def test_device_names_may_contain_dashes_and_digits(self):
        for key, device in (
            ("RPI-10-2026-06-14", "RPI-10"),
            ("home-server-2-2026-01-01", "home-server-2"),
            ("x-2026-06-14", "x"),
        ):
            with self.subTest(key=key):
                self.assertEqual(extract_device_name(key), device)

    def test_key_without_a_trailing_date_is_rejected(self):
        for key in (
            "stats",
            "test-node",
            "RPI-1",
            "RPI-1-2026-06",
            "RPI-1-2026-06-14-extra",
            "",
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    AttributeError, "not a valid Firebase node key"
                ):
                    extract_device_name(key)

    def test_date_is_matched_by_its_shape_only(self):
        # Documents the current behaviour: the date is not checked to be a real day.
        self.assertEqual(extract_device_name("RPI-1-2026-13-45"), "RPI-1")


class TestLoadRsaKeyFromFile(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.private_file = Path(folder) / "private_key.pem"
        self.public_file = Path(folder) / "public_key.pem"
        self.private_file.write_bytes(test_rsa_key().export_key())
        self.public_file.write_bytes(test_rsa_key().publickey().export_key())

    def test_private_and_public_keys_are_loaded(self):
        private = load_rsa_key_from_file(self.private_file)
        public = load_rsa_key_from_file(self.public_file)

        self.assertTrue(private.has_private())
        self.assertFalse(public.has_private())
        self.assertEqual(public, test_rsa_key().publickey())

    def test_keys_from_files_work_together(self):
        # As in production: the collector encrypts with the public file, the aggregator decrypts.
        public = load_rsa_key_from_file(self.public_file)
        private = load_rsa_key_from_file(self.private_file)

        self.assertEqual(
            decrypt_data(private, encrypt_data(public, "00:1A:2B:3C:4D:5E")),
            "00:1A:2B:3C:4D:5E",
        )

    def test_missing_file_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            load_rsa_key_from_file(self.private_file.with_name("missing.pem"))

    def test_file_that_is_not_a_key_is_an_error(self):
        self.private_file.write_text("not a key")

        with self.assertRaises(ValueError):
            load_rsa_key_from_file(self.private_file)


class TestDevice(unittest.TestCase):
    def test_devices_and_their_node_names(self):
        self.assertEqual(
            [device.value for device in Device], ["RPI-1", "RPI-2", "RPI-3"]
        )

    def test_device_from_a_node_key(self):
        self.assertIs(Device(extract_device_name("RPI-2-2026-06-14")), Device.RPI_2)


if __name__ == "__main__":
    unittest.main()
