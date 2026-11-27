"""Unit tests for the housekeeping DELETE /delete workflow, with Firebase, MongoDB and Mattermost replaced."""

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from tests.support.housekeeping_loader import import_housekeeping_module

main = import_housekeeping_module("firebase_housekeeping.main")
mongo_helpers = import_housekeeping_module("firebase_housekeeping.core.mongo.helpers")

WEBHOOK = "https://mattermost.test/hooks/housekeeping"
BACKUP = {"RPI-1": [{"data": {"e0": {"ssid": "CERN"}}}]}


class HousekeepingApiTestCase(unittest.TestCase):
    def setUp(self):
        # One parent mock, so the order of the calls across functions can be checked.
        self.workflow = mock.Mock()
        self.workflow.download_all.return_value = BACKUP
        for name in (
            "download_all",
            "insert_from_firebase_to_mongo",
            "delete_all_by_entry_nodes",
            "send_webhook_message",
        ):
            self.patch(name, getattr(self.workflow, name))
        self.patch("SLACK_WEBHOOK_URL", WEBHOOK)
        self.patch("MONGO_BACKUP", True)
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def patch(self, name, value):
        patcher = mock.patch.object(main, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def steps(self) -> list[str]:
        return [call[0] for call in self.workflow.mock_calls if call[0]]

    def messages(self) -> list[str]:
        return [
            call.args[0] for call in self.workflow.send_webhook_message.call_args_list
        ]


class TestDeleteWorkflow(HousekeepingApiTestCase):
    def test_backs_up_then_deletes(self):
        response = self.client.delete("/delete")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.steps(),
            [
                "send_webhook_message",
                "download_all",
                "insert_from_firebase_to_mongo",
                "delete_all_by_entry_nodes",
                "send_webhook_message",
            ],
        )

    def test_the_downloaded_data_is_what_is_backed_up(self):
        self.client.delete("/delete")

        self.workflow.insert_from_firebase_to_mongo.assert_called_once_with(BACKUP)

    def test_start_and_end_are_announced_by_the_housekeeping_bot(self):
        self.client.delete("/delete")

        self.assertEqual(
            self.messages(),
            [
                "Firebase delete workflow started.",
                "Firebase delete workflow completed.",
            ],
        )
        for call in self.workflow.send_webhook_message.call_args_list:
            self.assertEqual(call.kwargs["webhook"], WEBHOOK)
            self.assertEqual(call.kwargs["bot_name"], main.MattermostBot.HOUSEKEEPING)

    def test_backup_is_skipped_when_turned_off(self):
        self.patch("MONGO_BACKUP", False)

        self.client.delete("/delete")

        self.workflow.download_all.assert_not_called()
        self.workflow.insert_from_firebase_to_mongo.assert_not_called()
        self.workflow.delete_all_by_entry_nodes.assert_called_once()

    def test_failed_delete_returns_an_error_and_is_not_announced_as_completed(self):
        self.workflow.delete_all_by_entry_nodes.side_effect = RuntimeError("Too large")

        response = self.client.delete("/delete")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.messages(), ["Firebase delete workflow started."])

    def test_failed_download_stops_before_anything_is_deleted(self):
        self.workflow.download_all.side_effect = AttributeError("Not a node key")

        response = self.client.delete("/delete")

        self.assertEqual(response.status_code, 500)
        self.workflow.delete_all_by_entry_nodes.assert_not_called()

    def test_failed_start_message_stops_before_anything_is_deleted(self):
        self.workflow.send_webhook_message.side_effect = ValueError(
            "Mattermost is down"
        )

        self.client.delete("/delete")

        self.workflow.download_all.assert_not_called()
        self.workflow.delete_all_by_entry_nodes.assert_not_called()


class TestDeleteWorkflowKnownBugs(HousekeepingApiTestCase):
    @unittest.expectedFailure
    def test_failed_backup_stops_before_anything_is_deleted(self):
        """Known bug: insert_from_firebase_to_mongo logs upload errors and returns, so Firebase is
        deleted without a backup. Remove the decorator once a failed backup stops the delete.
        """
        bucket = mock.Mock()
        bucket.upload_from_stream.side_effect = ConnectionError(
            "MongoDB is unreachable"
        )
        self.patch(
            "insert_from_firebase_to_mongo", mongo_helpers.insert_from_firebase_to_mongo
        )

        with mock.patch.object(
            mongo_helpers, "get_bucket_for_write", return_value=bucket
        ):
            self.client.delete("/delete")

        self.workflow.delete_all_by_entry_nodes.assert_not_called()

    @unittest.expectedFailure
    def test_failed_completion_message_does_not_fail_a_finished_workflow(self):
        """Known bug: a Mattermost error after the delete returns a 500, so the orchestrator retries
        the whole workflow. Remove the decorator once notification errors are only logged.
        """
        self.workflow.send_webhook_message.side_effect = [
            None,
            ValueError("Mattermost is down"),
        ]

        response = self.client.delete("/delete")

        self.assertEqual(response.status_code, 200)

    @unittest.expectedFailure
    def test_other_websites_cannot_send_the_delete(self):
        """Known issue: CORS allows every origin, so any web page opened on the home network can
        wipe Firebase. Remove the decorator once cross-origin requests are refused.
        """
        response = self.client.options(
            "/delete",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "DELETE",
            },
        )

        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
