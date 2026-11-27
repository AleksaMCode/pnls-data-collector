"""Unit tests for sending the agent's metrics to Datadog, with the Datadog client replaced."""

import copy
import unittest
from unittest import mock

from tests.support.metrics_agent_loader import import_metrics_agent_module

helpers = import_metrics_agent_module("collector_metrics_agent.datadog.helpers")

DEVICE = "RPI-3"


def metric(**fields) -> dict:
    return {"metric": "pnls.cpu.user", "points": [(1_750_000_000.0, 12.5)], **fields}


class TestSendMetrics(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(helpers, "DEVICE_NAME", DEVICE)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(helpers, "api")
        self.api = patcher.start()
        self.addCleanup(patcher.stop)
        self.api.Metric.send.return_value = {"status": "ok"}

    def sent(self) -> list[dict]:
        self.api.Metric.send.assert_called_once()
        return self.api.Metric.send.call_args.args[0]

    def test_host_tag_is_replaced_by_the_configured_device(self):
        helpers.send_metrics([metric(tags=["host:old-name", "device:/", "host:other"])])

        self.assertEqual(self.sent()[0]["tags"], ["device:/", f"host:{DEVICE}"])

    def test_metric_without_tags_gets_the_host_tag(self):
        helpers.send_metrics([metric()])

        self.assertEqual(self.sent()[0]["tags"], [f"host:{DEVICE}"])

    def test_host_is_set_to_the_configured_device(self):
        helpers.send_metrics([metric(host="old-name")])

        self.assertEqual(self.sent()[0]["host"], DEVICE)

    def test_type_defaults_to_gauge(self):
        helpers.send_metrics([metric(), metric(type="count")])

        self.assertEqual([sent["type"] for sent in self.sent()], ["gauge", "count"])

    def test_every_metric_is_sent_in_one_request(self):
        helpers.send_metrics([metric(), metric(metric="pnls.cpu.idle")])

        self.assertEqual(
            [sent["metric"] for sent in self.sent()], ["pnls.cpu.user", "pnls.cpu.idle"]
        )

    def test_the_given_metrics_are_not_changed(self):
        given = [metric(tags=["host:old-name", "device:/"])]
        original = copy.deepcopy(given)

        helpers.send_metrics(given)

        self.assertEqual(given, original)

    def test_success_returns_true(self):
        self.assertTrue(helpers.send_metrics([metric()]))

    def test_client_error_returns_false_and_is_logged(self):
        self.api.Metric.send.side_effect = Exception("Connection reset")

        with self.assertLogs(helpers.logger, "ERROR") as logs:
            self.assertFalse(helpers.send_metrics([metric()]))

        self.assertIn("Connection reset", logs.output[0])

    @unittest.expectedFailure
    def test_rejected_metrics_return_false(self):
        """Known bug: the Datadog client is muted by default, so a rejected request (e.g. a bad
        API key) comes back as `{"errors": [...]}` instead of raising, and is reported as sent.
        Remove the decorator once the response is checked.
        """
        self.api.Metric.send.return_value = {"errors": ["Forbidden"]}

        self.assertFalse(helpers.send_metrics([metric()]))


if __name__ == "__main__":
    unittest.main()
