import json
import os
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace
from unittest import mock

from aggregator.core.orm.models import IEEERegistry
from aggregator.util import util as aggregator_util
from aggregator.util.util import (
    clean_string,
    get_channel,
    get_pending_import_dates,
    mac_normalize,
    mac_to_oui_candidates,
)
from tests.support.aggregator_loader import test_rsa_key
from util.util import encrypt_data, extract_device_name


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


class TestImportDateUtils(unittest.TestCase):

    def test_returns_empty_when_latest_import_is_today(self):
        latest_import_date = date(2026, 6, 14)
        current_date = date(2026, 6, 14)

        self.assertEqual(
            get_pending_import_dates(latest_import_date, current_date),
            [],
        )

    def test_returns_next_day_when_one_day_is_pending(self):
        latest_import_date = date(2026, 6, 13)
        current_date = date(2026, 6, 15)

        self.assertEqual(
            get_pending_import_dates(latest_import_date, current_date),
            [date(2026, 6, 14)],
        )

    def test_returns_all_missing_days_inclusive(self):
        latest_import_date = date(2026, 6, 10)
        current_date = date(2026, 6, 14)

        self.assertEqual(
            get_pending_import_dates(latest_import_date, current_date),
            [
                date(2026, 6, 11),
                date(2026, 6, 12),
                date(2026, 6, 13),
            ],
        )


class TestChannelUtils(unittest.TestCase):

    def test_get_channel_returns_valid_channels(self):
        self.assertEqual(get_channel(1), 1)
        self.assertEqual(get_channel(14), 14)
        self.assertEqual(get_channel("11"), 11)

    def test_get_channel_returns_none_for_invalid_values(self):
        self.assertIsNone(get_channel(None))
        self.assertIsNone(get_channel(""))
        self.assertIsNone(get_channel("abc"))
        self.assertIsNone(get_channel(0))
        self.assertIsNone(get_channel(15))
        self.assertIsNone(get_channel(124))


class UtilPatchMixin:
    """With ENV=test, aggregator/util/util.py skips importing tqdm, geopy and two settings,
    so the tests provide them (`create=True`)."""

    def patch_util(self, name, **kwargs):
        patcher = mock.patch.object(aggregator_util, name, create=True, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched


class TestMattermostMessages(UtilPatchMixin, unittest.TestCase):
    TOTALS = {"total_count": 1234567, "mac_count": 8901, "ssid_count": 23}

    def setUp(self):
        self.send = self.patch_util("send_webhook_message")
        self.patch_util("SLACK_WEBHOOK_URL", new="https://chat.test/hook")

    def test_daily_summary(self):
        aggregator_util.publish_to_channel(self.TOTALS, 4321)

        self.send.assert_called_once_with(
            "**Today's data has been aggregated.**\n"
            "(Captured Probe Requests: **4,321**)\n"
            "* Total captured probe requests: 1,234,567\n"
            "* Total captured unique MAC addresses: 8,901\n"
            "* Total captured unique SSIDs: 23\n",
            webhook="https://chat.test/hook",
        )

    def test_summary_for_an_imported_date(self):
        aggregator_util.publish_to_channel(self.TOTALS, 0, date(2026, 6, 14))

        message = self.send.call_args.args[0]
        self.assertTrue(
            message.startswith("**Data imported for date '2026-06-14'.**\n")
        )

    def test_missing_total_raises(self):
        with self.assertRaises(KeyError):
            aggregator_util.publish_to_channel({"total_count": 1}, 0)
        self.send.assert_not_called()

    def test_plain_message(self):
        aggregator_util.publish_message_to_channel("Import started.")

        self.send.assert_called_once_with(
            "Import started.", webhook="https://chat.test/hook"
        )


class TestParseDataLocal(UtilPatchMixin, unittest.TestCase):
    def setUp(self):
        self.patch_util("RSA_KEY_PATH", new="private_key.pem")
        self.patch_util("load_rsa_key_from_file", return_value=test_rsa_key())
        self.patch_util("tqdm", new=lambda iterable, **kwargs: iterable)

        # The device name is taken from the first five characters of the file name,
        # so the file is opened by its bare name from inside a temporary folder.
        folder = self.enterContext(tempfile.TemporaryDirectory())
        previous = os.getcwd()
        os.chdir(folder)
        self.addCleanup(os.chdir, previous)

    def write_records(self, file_name, *records):
        public_key = test_rsa_key().publickey()
        with open(file_name, "w", encoding="utf-8") as file:
            for record in records:
                record = dict(record, mac=encrypt_data(public_key, record["mac"]))
                file.write(json.dumps(record) + "\n")

    def test_decrypts_macs_cleans_ssids_and_sets_the_device(self):
        self.write_records(
            "RPI-2-export.json",
            {"mac": "00:11:22:33:44:55", "ssid": "CERN\x00", "channel": 6},
            {"mac": "66:77:88:99:AA:BB", "ssid": "eduroam", "channel": 11},
        )

        records = aggregator_util.parse_data_local("RPI-2-export.json")

        self.assertEqual(
            records,
            [
                {
                    "mac": "00:11:22:33:44:55",
                    "ssid": "CERN",
                    "channel": 6,
                    "device": "RPI-2",
                },
                {
                    "mac": "66:77:88:99:AA:BB",
                    "ssid": "eduroam",
                    "channel": 11,
                    "device": "RPI-2",
                },
            ],
        )

    def test_unreadable_file_returns_none(self):
        self.assertIsNone(aggregator_util.parse_data_local("RPI-1-missing.json"))


class TestGetCountryId(UtilPatchMixin, unittest.TestCase):
    def setUp(self):
        self.nominatim = self.patch_util("Nominatim")
        self.geocode = self.nominatim.return_value.geocode
        self.session = mock.MagicMock()
        self.lookup = self.session.query.return_value.filter_by

    def located_in(self, country):
        return SimpleNamespace(raw={"address": {"country": country}})

    def test_returns_the_id_of_the_geocoded_country(self):
        self.geocode.return_value = self.located_in("Switzerland")
        self.lookup.return_value.one_or_none.return_value = SimpleNamespace(id=41)

        country_id = aggregator_util.get_country_id(
            self.session, "Geneva", user_agent="pnls-test"
        )

        self.assertEqual(country_id, 41)
        self.nominatim.assert_called_once_with(user_agent="pnls-test")
        self.geocode.assert_called_once_with("Geneva", language="en")
        self.lookup.assert_called_once_with(name="Switzerland")

    def test_unknown_country_in_the_database(self):
        self.geocode.return_value = self.located_in("Atlantis")
        self.lookup.return_value.one_or_none.return_value = None

        self.assertIsNone(aggregator_util.get_country_id(self.session, "Nowhere"))

    def test_no_location_or_no_country(self):
        for location in (None, SimpleNamespace(raw={}), self.located_in(None)):
            with self.subTest(location=location):
                self.geocode.return_value = location

                self.assertIsNone(aggregator_util.get_country_id(self.session, "?"))
        self.session.query.assert_not_called()

    def test_geocoding_error_returns_none(self):
        self.geocode.side_effect = TimeoutError("rate limited")

        self.assertIsNone(aggregator_util.get_country_id(self.session, "Geneva"))


if __name__ == "__main__":
    unittest.main()
