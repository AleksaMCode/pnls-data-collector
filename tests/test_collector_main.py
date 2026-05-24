import unittest
from unittest.mock import patch

from collector.main import parse_args


class TestCollectorMainArgParse(unittest.TestCase):

    def test_defaults_channel_hopping_disabled(self):
        with patch("sys.argv", ["collector.main"]):
            args = parse_args()

        self.assertIsNone(args.interface)
        self.assertFalse(args.channel_hopping)

    def test_parses_interface_with_short_flag(self):
        with patch("sys.argv", ["collector.main", "-i", "wlan1"]):
            args = parse_args()

        self.assertEqual(args.interface, "wlan1")
        self.assertFalse(args.channel_hopping)

    def test_enables_channel_hopping_with_canonical_flag(self):
        with patch("sys.argv", ["collector.main", "--channel-hopping"]):
            args = parse_args()

        self.assertTrue(args.channel_hopping)

if __name__ == "__main__":
    unittest.main()
