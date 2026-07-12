import hashlib
import hmac
import unittest

from stats.util.util import _canonicalize_mac, hash_mac_hmac_sha256


class TestCanonicalizeMac(unittest.TestCase):
    def test_canonicalize_mac_normalizes_colon_format(self):
        self.assertEqual(_canonicalize_mac("AA:BB:CC:DD:EE:FF"), "aabbccddeeff")
        self.assertEqual(_canonicalize_mac("aa:bb:cc:dd:ee:ff"), "aabbccddeeff")
        self.assertEqual(_canonicalize_mac(" 01:23:45:67:89:AB "), "0123456789ab")

    def test_canonicalize_mac_raises_for_none(self):
        with self.assertRaises(ValueError):
            _canonicalize_mac(None)

    def test_canonicalize_mac_raises_for_invalid_formats(self):
        invalid_values = [
            "",
            "aa-bb-cc-dd-ee-ff",
            "aabbccddeeff",
            "AA:BB:CC:DD:EE",
            "GG:11:22:33:44:55",
        ]
        for mac in invalid_values:
            with self.subTest(mac=mac):
                with self.assertRaises(ValueError):
                    _canonicalize_mac(mac)


class TestHashMacHmacSha256(unittest.TestCase):
    def test_hash_mac_hmac_sha256_matches_expected_digest(self):
        mac = "AA:BB:CC:DD:EE:FF"
        pepper = "unit-test-pepper"
        expected = hmac.new(
            pepper.encode("utf-8"),
            "aabbccddeeff".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(hash_mac_hmac_sha256(mac, pepper), expected)

    def test_hash_mac_hmac_sha256_is_format_stable(self):
        pepper = "unit-test-pepper"
        self.assertEqual(
            hash_mac_hmac_sha256("AA:BB:CC:DD:EE:FF", pepper),
            hash_mac_hmac_sha256("aa:bb:cc:dd:ee:ff", pepper),
        )

    def test_hash_mac_hmac_sha256_changes_when_pepper_changes(self):
        mac = "AA:BB:CC:DD:EE:FF"
        hash_one = hash_mac_hmac_sha256(mac, "pepper-one")
        hash_two = hash_mac_hmac_sha256(mac, "pepper-two")
        self.assertNotEqual(hash_one, hash_two)

    def test_hash_mac_hmac_sha256_raises_for_invalid_mac(self):
        with self.assertRaises(ValueError):
            hash_mac_hmac_sha256("aabbccddeeff", "pepper")


if __name__ == "__main__":
    unittest.main()
