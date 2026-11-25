"""Unit tests for the collector's main loop, status thread and packet capture setup."""

import unittest
from unittest import mock
from urllib.error import HTTPError

from tests.support.collector_loader import import_collector_module
from tests.support.probe_capture import beacon, probe_request

sniffer = import_collector_module("collector.sniffer")


class StopLoop(BaseException):
    """Ends the collector's endless loops in tests. Not an Exception, so they cannot catch it."""


class SnifferTestCase(unittest.TestCase):
    def patch_sniffer(self, name, **kwargs):
        patcher = mock.patch.object(sniffer, name, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched


class TestStart(SnifferTestCase):
    def setUp(self):
        self.check_interface = self.patch_sniffer(
            "check_interface_mode", return_value=True
        )
        self.threads = self.patch_sniffer("threading").Thread
        self.threads.side_effect = lambda **kwargs: mock.MagicMock(kwargs=kwargs)
        self.capture = self.patch_sniffer("capture_traffic")
        self.capture.side_effect = KeyboardInterrupt
        self.run = self.patch_sniffer("subprocess").run
        self.sleep = self.patch_sniffer("time").sleep

    def start(self):
        with self.assertRaises(SystemExit) as raised:
            sniffer.start()
        return raised.exception.code

    def started_threads(self) -> dict:
        return {
            call.kwargs["target"]: call.kwargs for call in self.threads.call_args_list
        }

    def test_ctrl_c_exits_with_code_130(self):
        self.assertEqual(self.start(), 130)

    def test_starts_the_status_and_channel_hopper_threads(self):
        self.start()

        threads = self.started_threads()
        self.assertEqual(set(threads), {sniffer.send_status, sniffer.channel_hopper})
        self.assertEqual(
            threads[sniffer.channel_hopper]["args"],
            (
                sniffer.wifi_helpers.INTERFACE,
                sniffer.CHANNEL_HOP_INTERVAL,
                sniffer.CHANNELS,
            ),
        )
        self.assertTrue(threads[sniffer.channel_hopper]["daemon"])

    def test_both_threads_are_started(self):
        created = []

        def make_thread(**kwargs):
            thread = mock.MagicMock()
            created.append(thread)
            return thread

        self.threads.side_effect = make_thread

        self.start()

        self.assertEqual(len(created), 2)
        for thread in created:
            thread.start.assert_called_once()

    def test_capture_restarts_after_errors(self):
        self.capture.side_effect = [
            HTTPError("https://firebase.test", 503, "Unavailable", None, None),
            RuntimeError("interface went down"),
            KeyboardInterrupt,
        ]

        self.assertEqual(self.start(), 130)
        self.assertEqual(self.capture.call_count, 3)

    def test_reboots_when_no_interface_is_in_monitor_mode(self):
        self.check_interface.return_value = False

        self.start()

        self.run.assert_called_once_with(["sudo", "reboot"])

    @unittest.expectedFailure
    def test_stops_after_asking_for_a_reboot(self):
        """Known bug: start() carries on after `sudo reboot` and captures on an empty interface
        name. Remove the decorator once it stops there."""
        self.check_interface.return_value = False

        try:
            sniffer.start()
        except SystemExit:
            pass

        self.threads.assert_not_called()
        self.capture.assert_not_called()

    @unittest.expectedFailure
    def test_status_thread_does_not_keep_the_process_alive(self):
        """Known bug: the status thread is not a daemon and never ends, so the process keeps
        running after Ctrl-C. Remove the decorator once it is a daemon or can be stopped.
        """
        self.start()

        self.assertTrue(self.started_threads()[sniffer.send_status]["daemon"])

    @unittest.expectedFailure
    def test_waits_before_restarting_a_failed_capture(self):
        """Known bug: a capture that fails at once is restarted at once, over and over.
        Remove the decorator once the loop pauses before restarting."""
        self.capture.side_effect = [
            RuntimeError("interface went down"),
            KeyboardInterrupt,
        ]

        self.start()

        self.sleep.assert_called()


class TestCaptureTraffic(SnifferTestCase):
    def setUp(self):
        self.async_sniffer = self.patch_sniffer("AsyncSniffer")
        patcher = mock.patch.object(sniffer.wifi_helpers, "INTERFACE", "wlan1mon")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_captures_probe_requests_on_the_monitor_interface(self):
        sniffer.capture_traffic()

        kwargs = self.async_sniffer.call_args.kwargs
        self.assertEqual(kwargs["iface"], "wlan1mon")
        self.assertIs(kwargs["prn"], sniffer.parse_ip_packet)
        self.assertFalse(kwargs["store"])
        self.assertEqual(kwargs["filter"], "type mgt subtype probe-req")
        self.async_sniffer.return_value.start.assert_called_once()
        self.async_sniffer.return_value.join.assert_called_once()

    def test_frame_filter_keeps_only_probe_requests(self):
        sniffer.capture_traffic()
        keep = self.async_sniffer.call_args.kwargs["lfilter"]

        self.assertTrue(keep(probe_request("00:11:22:33:44:55", b"CERN")))
        self.assertFalse(keep(beacon("aa:bb:cc:dd:ee:ff", b"CERN")))


class TestSendStatus(SnifferTestCase):
    def setUp(self):
        self.update = self.patch_sniffer("update_device_status")
        self.sleep = self.patch_sniffer("time").sleep

    def test_updates_the_status_then_waits(self):
        self.sleep.side_effect = StopLoop

        with self.assertRaises(StopLoop):
            sniffer.send_status()

        self.update.assert_called_once_with()
        self.sleep.assert_called_once_with(sniffer.FIREBASE_TIMEOUT_STATUS)

    def test_failed_update_is_logged_and_retried(self):
        self.update.side_effect = [ConnectionError("Firebase down"), StopLoop()]

        with self.assertRaises(StopLoop):
            sniffer.send_status()

        self.assertEqual(self.update.call_count, 2)

    @unittest.expectedFailure
    def test_failed_update_waits_before_retrying(self):
        """Known bug: the wait is skipped when the update fails, so it retries in a tight loop.
        Remove the decorator once it always waits."""
        self.update.side_effect = [ConnectionError("Firebase down"), StopLoop()]

        with self.assertRaises(StopLoop):
            sniffer.send_status()

        self.sleep.assert_called_once_with(sniffer.FIREBASE_TIMEOUT_STATUS)


if __name__ == "__main__":
    unittest.main()
