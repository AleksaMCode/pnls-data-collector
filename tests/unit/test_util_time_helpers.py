import unittest
from datetime import datetime
from unittest.mock import patch

import util.util as util_module


class TestTimeHelpers(unittest.TestCase):
    def test_is_working_hours_true_at_boundaries(self):
        with patch("util.util.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 7, 4, 7, 0, 0)
            self.assertTrue(util_module.is_working_hours())

            mock_datetime.now.return_value = datetime(2026, 7, 4, 18, 0, 0)
            self.assertTrue(util_module.is_working_hours())

    def test_is_working_hours_false_outside_boundaries(self):
        with patch("util.util.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 7, 4, 6, 59, 59)
            self.assertFalse(util_module.is_working_hours())

            mock_datetime.now.return_value = datetime(2026, 7, 4, 18, 0, 1)
            self.assertFalse(util_module.is_working_hours())

    def test_is_after_six_false_at_six_pm(self):
        with patch("util.util.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 7, 4, 18, 0, 0)
            self.assertFalse(util_module.is_after_six())

    def test_is_after_six_true_after_six_pm(self):
        with patch("util.util.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 7, 4, 18, 0, 1)
            self.assertTrue(util_module.is_after_six())


if __name__ == "__main__":
    unittest.main()
