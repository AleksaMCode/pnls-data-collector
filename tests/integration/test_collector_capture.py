"""Integration tests for the collector's capture path, with the Firebase Database emulator."""

import json
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scapy.sendrecv import sniff

from tests.integration.containers import (
    assert_firebase_is_emulator,
    connect_firebase_emulator,
    requires_firebase,
)
from tests.support import aggregator_loader
from tests.support.collector_loader import import_collector_module
from tests.support.keys import test_rsa_key
from tests.support.probe_capture import (
    beacon,
    is_probe_request,
    probe_request,
    write_capture,
)
from util.util import decrypt_data

PARIS = ZoneInfo("Europe/Paris")
FILTERED_MAC = "00:1a:2b:00:00:99"
HOPPING_CHANNEL = 9


def frozen_host_clock(day: date):
    """A `datetime` whose `now()` is noon on `day`, as if the collector ran on that day."""
    noon = datetime.combine(day, time(12, 0), tzinfo=PARIS)

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return noon.astimezone(tz) if tz else noon.replace(tzinfo=None)

    return FrozenClock


@requires_firebase
class CollectorCaptureTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parser = import_collector_module("collector.wlan.parser")
        cls.collector_firebase = import_collector_module(
            "collector.core.firebase.helpers"
        )
        cls.backup = import_collector_module("collector.util.util")
        cls.aggregator_firebase = aggregator_loader.import_firebase_helpers()
        connect_firebase_emulator()
        cls.db = cls.collector_firebase.db

    def setUp(self):
        super().setUp()
        assert_firebase_is_emulator()
        self.db.reference("/").delete()
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))

        parser, wifi = self.parser, self.parser.wifi_helpers
        for target, name, value in (
            (parser, "RSA_KEY", test_rsa_key().publickey()),
            (parser, "CAPTURE_24_7", True),
            (parser, "SSID_FILTER", []),
            (parser, "MAC_FILTER", [FILTERED_MAC]),
            (parser, "TIMEZONE", "Europe/Paris"),
            (wifi, "WLAN_CHANNEL", HOPPING_CHANNEL),
            (wifi, "CHANNELS", range(1, 14)),
            (self.collector_firebase, "FIREBASE_NODE", "RPI-1"),
            (self.collector_firebase, "TIMEZONE", "Europe/Paris"),
            (self.backup, "DATA_DIR", str(self.folder)),
            (self.aggregator_firebase, "RSA_KEY", test_rsa_key()),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def capture(self, packets, *, device="RPI-1", day: date | None = None):
        """Writes the frames to a .pcap file and runs them through the collector, as the
        sniffer does with a live capture. `day` runs the collector as if it were that day.
        """
        path = write_capture(self.folder / f"{device}.pcap", packets)
        with mock.patch.object(self.collector_firebase, "FIREBASE_NODE", device):
            clock = (
                mock.patch.object(self.parser, "datetime", frozen_host_clock(day))
                if day
                else mock.patch.object(self.parser, "datetime", datetime)
            )
            with clock:
                sniff(
                    offline=str(path),
                    prn=self.parser.parse_ip_packet,
                    lfilter=is_probe_request,
                    store=False,
                )

    def firebase_records(self, node: str) -> list[dict]:
        data = self.db.reference(f"/{node}/data").get() or {}
        return sorted(data.values(), key=lambda record: record["timestamp"])


def sample_capture(day: date) -> list:
    """Frames covering what the collector records, rewrites and drops, at 10:00 on `day`."""

    def at(minute):
        return datetime.combine(day, time(10, minute), tzinfo=PARIS)

    return [
        probe_request("00:1a:2b:00:00:01", b"CERN-Guest", frequency=2412, at=at(0)),
        probe_request("00:1a:2b:00:00:02", b"", ds_channel=6, at=at(1)),
        probe_request("02:00:00:00:00:03", b"\xff\xfe", at=at(2)),
        beacon("aa:bb:cc:dd:ee:ff", b"Access point", at=at(3)),  # Not a probe request.
        probe_request(FILTERED_MAC, b"CERN-Guest", frequency=2412, at=at(4)),
    ]


# (MAC, SSID, channel, time) of what the collector records from sample_capture().
EXPECTED_RECORDS = [
    ("00:1a:2b:00:00:01", "CERN-Guest", 1, "10:00:00.000"),
    ("00:1a:2b:00:00:02", "*", 6, "10:01:00.000"),  # Wildcard probe request.
    ("02:00:00:00:00:03", "*", HOPPING_CHANNEL, "10:02:00.000"),  # Undecodable SSID.
]


class TestCollectorFirebase(CollectorCaptureTestCase):
    def test_records_are_pushed_under_the_node_of_the_day(self):
        first = {"mac": "a", "ssid": "CERN", "channel": 1, "timestamp": "t1"}
        second = {"mac": "b", "ssid": "eduroam", "channel": 6, "timestamp": "t2"}

        self.collector_firebase.publish_captured_date(first, "2026-06-14")
        self.collector_firebase.publish_captured_date(second, "2026-06-14")

        data = self.db.reference("/RPI-1-2026-06-14/data").get()
        self.assertCountEqual(data.values(), [first, second])
        # Firebase push IDs start with "-" and sort by creation time.
        self.assertTrue(all(key.startswith("-") for key in data))
        self.assertEqual([data[key] for key in sorted(data)], [first, second])

    def test_device_status(self):
        self.collector_firebase.update_device_status()

        today = datetime.now(PARIS).date()
        status = self.db.reference(f"/RPI-1-{today}/status").get()
        self.assertEqual(status["status"], "working")
        self.assertTrue(status["timestamp"].startswith(str(today)))


class TestOfflineCapture(CollectorCaptureTestCase):
    def test_captured_frames_reach_firebase(self):
        today = date.today()

        self.capture(sample_capture(today))

        records = self.firebase_records(f"RPI-1-{today}")
        self.assertEqual(
            [
                (
                    decrypt_data(test_rsa_key(), record["mac"]),
                    record["ssid"],
                    record["channel"],
                    record["timestamp"],
                )
                for record in records
            ],
            [
                (mac, ssid, channel, f"{today} {clock}")
                for mac, ssid, channel, clock in EXPECTED_RECORDS
            ],
        )

    def test_local_backup_matches_firebase(self):
        today = date.today()

        self.capture(sample_capture(today))

        backup_file = self.folder / f"{today}-data.json"
        backed_up = [
            json.loads(line)
            for line in backup_file.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(backed_up, self.firebase_records(f"RPI-1-{today}"))


class TestCollectorAggregatorContract(CollectorCaptureTestCase):
    """What the collector writes is exactly what the aggregator reads back."""

    def test_aggregator_reads_what_the_collector_captured(self):
        day = datetime.now(PARIS).date() - timedelta(days=1)
        self.capture(sample_capture(day), device="RPI-1", day=day)
        self.capture(
            [
                probe_request(
                    "00:1a:2b:00:00:05",
                    b"Home",
                    frequency=2462,
                    at=datetime.combine(day, time(11, 0), tzinfo=PARIS),
                )
            ],
            device="RPI-3",
            day=day,
        )

        records = self.aggregator_firebase.fetch_data(day)

        self.assertEqual(
            [
                (r["device"], r["mac"], r["ssid"], r["channel"], r["timestamp"])
                for r in records
            ],
            [
                ("RPI-1", mac, ssid, channel, f"{day} {clock}")
                for mac, ssid, channel, clock in EXPECTED_RECORDS
            ]
            + [("RPI-3", "00:1a:2b:00:00:05", "Home", 11, f"{day} 11:00:00.000")],
        )

    def test_aggregator_can_parse_the_collector_timestamps(self):
        day = datetime.now(PARIS).date() - timedelta(days=1)
        self.capture(sample_capture(day), day=day)

        timestamp_format = self.aggregator_firebase.TIMESTAMP_FORMAT
        for record in self.aggregator_firebase.fetch_data(day):
            with self.subTest(timestamp=record["timestamp"]):
                parsed = datetime.strptime(record["timestamp"], timestamp_format)
                self.assertEqual(parsed.date(), day)


if __name__ == "__main__":
    unittest.main()
