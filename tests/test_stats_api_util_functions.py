import unittest
from datetime import date, datetime
from unittest.mock import patch

from stats_api.util.util import (
    last_n_dates_excluding_today,
    previous_n_dates_before_last_n,
    scalar_to_int,
    today_in_tz,
)


class TestScalarToInt(unittest.TestCase):
    def test_scalar_to_int_converts_numbers_and_strings(self):
        self.assertEqual(scalar_to_int(5), 5)
        self.assertEqual(scalar_to_int("7"), 7)

    def test_scalar_to_int_defaults_falsy_values_to_zero(self):
        self.assertEqual(scalar_to_int(None), 0)
        self.assertEqual(scalar_to_int(""), 0)
        self.assertEqual(scalar_to_int(False), 0)


class TestDateHelpers(unittest.TestCase):
    @patch("stats_api.util.util.ZoneInfo")
    @patch("stats_api.util.util.datetime")
    def test_today_in_tz_uses_requested_timezone_and_returns_date(
        self, mock_datetime, mock_zone_info
    ):
        mock_zone_info.return_value = "tz-object"
        mock_datetime.now.return_value = datetime(2026, 7, 13, 11, 30, 0)

        result = today_in_tz("UTC")

        self.assertEqual(result, date(2026, 7, 13))
        mock_zone_info.assert_called_once_with("UTC")
        mock_datetime.now.assert_called_once_with("tz-object")

    @patch("stats_api.util.util.today_in_tz")
    def test_last_n_dates_excluding_today_returns_expected_order(
        self, mock_today_in_tz
    ):
        mock_today_in_tz.return_value = date(2026, 7, 13)

        result = last_n_dates_excluding_today(3, "Europe/Paris")

        self.assertEqual(
            result,
            [
                date(2026, 7, 10),
                date(2026, 7, 11),
                date(2026, 7, 12),
            ],
        )
        mock_today_in_tz.assert_called_once_with("Europe/Paris")

    @patch("stats_api.util.util.today_in_tz")
    def test_last_n_dates_excluding_today_zero_days_returns_empty(
        self, mock_today_in_tz
    ):
        mock_today_in_tz.return_value = date(2026, 7, 13)

        result = last_n_dates_excluding_today(0, "UTC")

        self.assertEqual(result, [])
        mock_today_in_tz.assert_called_once_with("UTC")

    @patch("stats_api.util.util.today_in_tz")
    def test_previous_n_dates_before_last_n_returns_expected_window(
        self, mock_today_in_tz
    ):
        mock_today_in_tz.return_value = date(2026, 7, 13)

        result = previous_n_dates_before_last_n(3, "Europe/Paris")

        self.assertEqual(
            result,
            [
                date(2026, 7, 7),
                date(2026, 7, 8),
                date(2026, 7, 9),
            ],
        )
        mock_today_in_tz.assert_called_once_with("Europe/Paris")

    @patch("stats_api.util.util.today_in_tz")
    def test_previous_n_dates_before_last_n_zero_days_returns_empty(
        self, mock_today_in_tz
    ):
        mock_today_in_tz.return_value = date(2026, 7, 13)

        result = previous_n_dates_before_last_n(0, "UTC")

        self.assertEqual(result, [])
        mock_today_in_tz.assert_called_once_with("UTC")


if __name__ == "__main__":
    unittest.main()
