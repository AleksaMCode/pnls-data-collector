"""Integration tests of the metrics agent with real psutil readings and the real Datadog client against a local fake server."""

import json
import math
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock

import datadog.api

from tests.support.metrics_agent_fakes import StopLoop
from tests.support.metrics_agent_loader import import_metrics_agent_module

helpers = import_metrics_agent_module("collector_metrics_agent.datadog.helpers")
main = import_metrics_agent_module("collector_metrics_agent.main")

API_KEY = "test-api-key"
DEVICE = "RPI-TEST"
RATIO_METRICS = {"pnls.mem.pct_usable", "pnls.disk.in_use"}


class FakeDatadog(ThreadingHTTPServer):
    """Records each request and answers with `status` and `body`, like the Datadog API."""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), FakeDatadogHandler)
        self.requests = []
        self.status = 202
        self.body = {"status": "ok"}

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"


class FakeDatadogHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.server.requests.append(
            SimpleNamespace(
                path=self.path,
                headers=dict(self.headers),
                body=json.loads(self.rfile.read(length)),
            )
        )
        payload = json.dumps(self.server.body).encode()
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


def unused_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class DatadogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FakeDatadog()
        thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)

    def setUp(self):
        self.server.requests.clear()
        self.server.status = 202
        self.server.body = {"status": "ok"}
        self.point_client_at(self.server.url)
        patcher = mock.patch.object(helpers, "DEVICE_NAME", DEVICE)
        patcher.start()
        self.addCleanup(patcher.stop)

    def point_client_at(self, url: str):
        # The client reads these module settings on every request; `initialize()` sets them.
        for name, value in (
            ("_api_key", API_KEY),
            ("_api_host", url),
            ("_host_name", "not-the-device"),
            ("_mute", True),
            ("_max_retries", 0),
            ("_timeout", 5),
            ("_proxies", {"http": None, "https": None}),
        ):
            patcher = mock.patch.object(datadog.api, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.assertTrue(datadog.api._api_host.startswith("http://127.0.0.1:"))

    def series(self) -> list[dict]:
        self.assertEqual(len(self.server.requests), 1)
        return self.server.requests[0].body["series"]


class TestSendMetricsToDatadog(DatadogTestCase):
    def metric(self, **fields):
        return {
            "metric": "pnls.cpu.user",
            "points": [(1_750_000_000.0, 12.5)],
            "tags": ["host:old-name", "device:/"],
            **fields,
        }

    def test_metrics_are_posted_to_the_series_endpoint_with_the_api_key(self):
        self.assertTrue(helpers.send_metrics([self.metric()]))

        (request,) = self.server.requests
        self.assertEqual(request.path, "/api/v1/series")
        self.assertEqual(request.headers["DD-API-KEY"], API_KEY)

    def test_the_series_carries_the_device_tags_type_and_points(self):
        helpers.send_metrics([self.metric(), self.metric(metric="pnls.cpu.idle")])

        self.assertEqual(
            self.series(),
            [
                {
                    "metric": name,
                    "points": [[1_750_000_000.0, 12.5]],
                    "tags": ["device:/", f"host:{DEVICE}"],
                    "host": DEVICE,
                    "type": "gauge",
                }
                for name in ("pnls.cpu.user", "pnls.cpu.idle")
            ],
        )

    def test_server_error_returns_false(self):
        self.server.status = 500
        self.server.body = {"error": "Internal error"}

        self.assertFalse(helpers.send_metrics([self.metric()]))

    @unittest.expectedFailure
    def test_rejected_api_key_returns_false(self):
        """Known bug: the muted client returns a 403 as `{"errors": [...]}` instead of raising.
        Remove the decorator once the response is checked.
        """
        self.server.status = 403
        self.server.body = {"errors": ["Forbidden"]}

        self.assertFalse(helpers.send_metrics([self.metric()]))

    @unittest.expectedFailure
    def test_unreachable_datadog_returns_false(self):
        """Known bug: the muted client also returns a connection error as `{"errors": [...]}`.
        Remove the decorator once the response is checked.
        """
        self.point_client_at(f"http://127.0.0.1:{unused_port()}")

        self.assertFalse(helpers.send_metrics([self.metric()]))


class TestAgentEndToEnd(DatadogTestCase):
    """One iteration of `start()` on this machine: real psutil readings, the real Datadog client."""

    def run_one_iteration(self):
        def stop(seconds):
            raise StopLoop

        clock = SimpleNamespace(time=time.time, monotonic=time.monotonic, sleep=stop)
        with (
            mock.patch.object(main, "time", clock),
            mock.patch.object(main, "DEVICE_NAME", DEVICE),
            self.assertRaises(StopLoop),
        ):
            main.start()

    def test_one_iteration_sends_every_metric_for_the_device(self):
        self.run_one_iteration()

        series = self.series()
        self.assertEqual(len(series), 16)
        for metric in series:
            with self.subTest(metric=metric["metric"]):
                self.assertEqual(metric["host"], DEVICE)
                self.assertIn(f"host:{DEVICE}", metric["tags"])

    def test_every_reading_is_a_plausible_number(self):
        before = time.time()
        self.run_one_iteration()

        for metric in self.series():
            ((timestamp, value),) = metric["points"]
            with self.subTest(metric=metric["metric"]):
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, 0)
                self.assertAlmostEqual(timestamp, before, delta=5)
                if metric["metric"] in RATIO_METRICS:
                    self.assertLessEqual(value, 1)


if __name__ == "__main__":
    unittest.main()
