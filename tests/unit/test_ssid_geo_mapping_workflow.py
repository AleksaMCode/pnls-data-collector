"""Unit tests for the SSID GEO mapping run, with the database, WiGLE and Mattermost replaced."""

import os
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from tests.support.fake_http import unused_port
from tests.support.ssid_geo_loader import import_ssid_geo_module

main = import_ssid_geo_module("ssid_geo_mapper.main")
wigle_errors = import_ssid_geo_module("ssid_geo_mapper.exceptions.wigle")

WEBHOOK = "https://mattermost.test/hooks/ssid-geo"
LOCATIONS = [{"ssid": "home", "lat": 46.2, "long": 6.14, "alpha2": "CH"}]
REDUCED = LOCATIONS[:1]


def ssid(ssid_id: int, name: str, failed_attempts: int = 0):
    return SimpleNamespace(id=ssid_id, ssid=name, failed_attempts=failed_attempts)


class FakeWigle:
    """Answers each SSID from `answers`: a (locations, reduced) pair, or an exception to raise."""

    answers: dict = {}

    def __init__(self):
        self.request_count = 0
        self.looked_up = []
        FakeWigle.last = self

    def lookup_SSID(self, name):
        self.request_count += 1
        self.looked_up.append(name)
        answer = self.answers.get(name, ([], []))
        if isinstance(answer, Exception):
            raise answer
        return answer


class MappingTestCase(unittest.TestCase):
    def setUp(self):
        self.get_unmapped = self.patch("get_unmapped_ssids", return_value=[])
        self.insert = self.patch("insert_ssid_geo_batch")
        self.mark_mapped = self.patch("update_ssid_mapped")
        self.record_failure = self.patch("record_ssid_failure")
        self.send = self.patch("send_webhook_message")
        self.patch("Wigle", FakeWigle)
        self.patch("SLACK_WEBHOOK_URL", WEBHOOK)
        self.patch("WIGLE_BASE_DELAY_SECONDS", 2.0)
        self.patch("WIGLE_DELAY_JITTER_SECONDS", 0.5)
        self.sleep = mock.Mock()
        self.patch("time", SimpleNamespace(sleep=self.sleep, monotonic=time.monotonic))
        FakeWigle.answers = {}
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def patch(self, name, value=mock.DEFAULT, **kwargs):
        patcher = mock.patch.object(main, name, value, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def run_mapping(self, ssids, answers=None):
        self.get_unmapped.return_value = ssids
        FakeWigle.answers = answers or {}
        return self.client.post("/ssid_mapping")

    def summary(self) -> str:
        return self.send.call_args_list[-1].args[0]

    def recorded_failures(self) -> dict[int, str]:
        return {
            call.args[0]: call.args[1] for call in self.record_failure.call_args_list
        }


class TestMappingRun(MappingTestCase):
    def test_each_outcome_is_stored_and_counted(self):
        response = self.run_mapping(
            [
                ssid(1, "home"),
                ssid(2, "cafe"),
                ssid(3, "broken"),
                ssid(4, "slow"),
                ssid(5, "odd"),
                ssid(6, "boom"),
            ],
            {
                "home": (LOCATIONS, REDUCED),
                "cafe": ([], []),
                "broken": wigle_errors.WigleLookupError("500", status_code=500),
                "slow": httpx.ReadTimeout("timed out"),
                "odd": wigle_errors.WigleLookupError("no results", status_code=200),
                "boom": ValueError("unexpected"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.insert.assert_called_once_with(1, LOCATIONS, REDUCED)
        self.mark_mapped.assert_called_once_with(2, has_geo=False)
        self.assertEqual(
            self.recorded_failures(),
            {3: "500", 4: "timeout", 5: "bad payload", 6: "ValueError"},
        )
        self.assertIn("Attempted: 6 | Requests sent: 6/250", self.summary())
        self.assertIn("With locations: 1 | No results: 1 | Failed: 4", self.summary())

    def test_ssids_are_requested_with_the_batch_size(self):
        self.patch("WIGLE_BATCH_SIZE", 17)

        self.run_mapping([])

        self.get_unmapped.assert_called_once_with(17)

    def test_start_and_summary_are_sent_by_the_mapper_bot(self):
        self.run_mapping([ssid(1, "home")])

        self.assertEqual(self.send.call_count, 2)
        self.assertEqual(
            self.send.call_args_list[0].args[0], "SSID GEO mapping workflow started."
        )
        for call in self.send.call_args_list:
            self.assertEqual(call.kwargs["webhook"], WEBHOOK)
            self.assertEqual(
                call.kwargs["bot_name"], main.MattermostBot.SSID_GEO_MAPPER
            )

    def test_empty_queue_completes_with_nothing_attempted(self):
        self.run_mapping([])

        self.assertTrue(self.summary().startswith("SSID GEO mapping completed in"))
        self.assertIn("Attempted: 0", self.summary())

    def test_lookups_are_paced_but_not_before_the_first(self):
        self.run_mapping([ssid(1, "a"), ssid(2, "b"), ssid(3, "c")])

        self.assertEqual(self.sleep.call_count, 2)
        for call in self.sleep.call_args_list:
            self.assertGreaterEqual(call.args[0], 2.0)
            self.assertLessEqual(call.args[0], 2.5)

    def test_previously_failed_ssids_are_counted_as_retried(self):
        self.run_mapping([ssid(1, "a", failed_attempts=2), ssid(2, "b")])

        self.assertIn("Retried after earlier failure: 1", self.summary())

    def test_failure_that_cannot_be_recorded_does_not_stop_the_run(self):
        self.record_failure.side_effect = RuntimeError("database is down")

        self.run_mapping(
            [ssid(1, "broken"), ssid(2, "home")],
            {
                "broken": wigle_errors.WigleLookupError("500", status_code=500),
                "home": (LOCATIONS, REDUCED),
            },
        )

        self.insert.assert_called_once_with(2, LOCATIONS, REDUCED)

    def test_failed_insert_is_recorded_as_a_failure_of_the_ssid(self):
        self.insert.side_effect = RuntimeError("constraint violated")

        self.run_mapping([ssid(1, "home")], {"home": (LOCATIONS, REDUCED)})

        self.assertEqual(self.recorded_failures(), {1: "RuntimeError"})


class TestRunIsCutShort(MappingTestCase):
    def test_rate_limit_stops_the_run_and_leaves_the_ssid_unmapped(self):
        self.run_mapping(
            [ssid(1, "a"), ssid(2, "b"), ssid(3, "c")],
            {
                "a": (LOCATIONS, REDUCED),
                "b": wigle_errors.WigleRateLimitError(
                    "429", status_code=429, body="Too many queries", retry_after="3600"
                ),
            },
        )

        self.assertEqual(FakeWigle.last.looked_up, ["a", "b"])
        self.record_failure.assert_not_called()
        self.assertIn("ABORTED", self.summary())
        self.assertIn("429 from WiGLE at request 2/250", self.summary())
        self.assertIn("Retry-After: 3600", self.summary())
        self.assertIn("WiGLE said: Too many queries", self.summary())

    def test_access_denied_stops_the_run(self):
        self.run_mapping(
            [ssid(1, "a"), ssid(2, "b")],
            {"a": wigle_errors.WigleAccessDeniedError("403", status_code=403)},
        )

        self.assertEqual(FakeWigle.last.looked_up, ["a"])
        self.record_failure.assert_not_called()
        self.assertIn("403 from WiGLE at request 1/250", self.summary())

    def test_run_stops_at_the_request_budget(self):
        self.patch("WIGLE_API_LIMIT", 2)

        self.run_mapping([ssid(1, "a"), ssid(2, "b"), ssid(3, "c")])

        self.assertEqual(FakeWigle.last.looked_up, ["a", "b"])
        self.assertIn("STOPPED", self.summary())
        self.assertIn("request budget of 2 reached", self.summary())


class TestMappingRunKnownBugs(MappingTestCase):
    @unittest.expectedFailure
    def test_unreachable_wigle_stops_the_run_without_blaming_the_ssids(self):
        """Known bug: a connection error is recorded against every SSID of the batch, and the run
        goes on. Remove the decorator once such errors stop the run like a 429.
        """
        outage = httpx.ConnectError("Name or service not known")

        self.run_mapping(
            [ssid(1, "a"), ssid(2, "b"), ssid(3, "c")],
            {"a": outage, "b": outage, "c": outage},
        )

        self.record_failure.assert_not_called()
        self.assertEqual(FakeWigle.last.looked_up, ["a"])

    @unittest.expectedFailure
    def test_missing_credentials_fail_the_run_before_any_ssid(self):
        """Known bug: without credentials httpx raises TypeError for each SSID, and every SSID is
        recorded as failed. Remove the decorator once the credentials are checked up front.
        """
        wigle = _real_wigle()
        self.patch("Wigle", wigle)
        # Nothing listens there, so no request can reach the real WiGLE API.
        url = mock.patch.object(
            wigle, "URL", f"http://127.0.0.1:{unused_port()}/search"
        )
        self.enterContext(url)

        with mock.patch.dict("os.environ"):
            for name in ("WIGLE_API_KEY", "WIGLE_API_SECRET"):
                os.environ.pop(name, None)
            self.run_mapping([ssid(1, "a"), ssid(2, "b")])

        self.record_failure.assert_not_called()

    @unittest.expectedFailure
    def test_failed_queue_query_still_sends_a_summary(self):
        """Known bug: when the database query fails, only the start message is sent. Remove the
        decorator once a failed run is reported too.
        """
        self.get_unmapped.side_effect = RuntimeError("database is down")

        self.client.post("/ssid_mapping")

        self.assertEqual(self.send.call_count, 2)

    @unittest.expectedFailure
    def test_failed_summary_message_does_not_fail_a_finished_run(self):
        """Known bug: a Mattermost error on the summary turns a finished run into a 500. Remove the
        decorator once notification errors are only logged.
        """
        self.send.side_effect = [None, ValueError("Mattermost is down")]

        response = self.run_mapping([ssid(1, "home")], {"home": (LOCATIONS, REDUCED)})

        self.assertEqual(response.status_code, 200)


def _real_wigle():
    return import_ssid_geo_module("ssid_geo_mapper.wigle_adapter.wigle").Wigle


if __name__ == "__main__":
    unittest.main()
