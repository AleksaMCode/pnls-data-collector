"""Unit tests for the Mattermost webhook helper, against a local fake webhook."""

import unittest
from unittest import mock

import requests

from tests.support.fake_http import FakeMattermost, start_in_background, unused_port
from util.mattermost import helpers as mattermost

ICONS = "https://raw.githubusercontent.com/AleksaMCode/pnls-data-collector/master/resources/bot_icons/"


class TestSendWebhookMessage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.webhook = FakeMattermost()
        start_in_background(cls.webhook, cls)

    def setUp(self):
        self.webhook.messages.clear()
        self.webhook.headers.clear()
        self.webhook.status = 200
        self.webhook.reply = b"ok"
        # Under ENV=test, util.mattermost.helpers does not import requests.
        self.enterContext(
            mock.patch.object(mattermost, "requests", requests, create=True)
        )

    def send(self, message="Import completed.", **kwargs):
        mattermost.send_webhook_message(message, webhook=self.webhook.url, **kwargs)

    def test_message_is_posted_as_json(self):
        self.send(bot_name=mattermost.MattermostBot.HOUSEKEEPING)

        self.assertEqual(
            self.webhook.messages,
            [
                {
                    "text": "Import completed.",
                    "username": "Housekeeping",
                    "icon_url": f"{ICONS}housekeeping.png",
                }
            ],
        )
        self.assertEqual(self.webhook.headers[0]["Content-Type"], "application/json")

    def test_each_bot_has_its_own_name_and_icon(self):
        for bot, icon in (
            (mattermost.MattermostBot.AGGREGATOR, "aggregator.png"),
            (mattermost.MattermostBot.HOUSEKEEPING, "housekeeping.png"),
            (mattermost.MattermostBot.SSID_GEO_MAPPER, "ssid_geo_mapper.png"),
        ):
            with self.subTest(bot=bot):
                self.webhook.messages.clear()

                self.send(bot_name=bot)

                (message,) = self.webhook.messages
                self.assertEqual(message["username"], bot.value)
                self.assertEqual(message["icon_url"], f"{ICONS}{icon}")

    def test_aggregator_is_the_default_bot(self):
        self.send()

        self.assertEqual(self.webhook.messages[0]["username"], "Aggregator")

    def test_multi_line_and_non_ascii_text_is_sent_as_is(self):
        self.send("Résumé:\n  SSIDs: 42 ✓")

        self.assertEqual(self.webhook.messages[0]["text"], "Résumé:\n  SSIDs: 42 ✓")

    def test_success_is_logged(self):
        with self.assertLogs(mattermost.logger, "INFO") as logs:
            self.send()

        self.assertIn("message sent to Mattermost", logs.output[0])

    def test_error_reply_raises_with_its_status_and_body(self):
        self.webhook.status = 400
        self.webhook.reply = b"Unable to parse incoming data"

        with self.assertRaisesRegex(ValueError, "error 400") as error:
            self.send()

        self.assertIn("Unable to parse incoming data", str(error.exception))

    def test_request_times_out_after_10_seconds(self):
        with mock.patch.object(requests, "post", wraps=requests.post) as post:
            self.send()

        self.assertEqual(post.call_args.kwargs["timeout"], 10)

    def test_unreachable_webhook_raises(self):
        with self.assertRaises(requests.ConnectionError):
            mattermost.send_webhook_message(
                "Import completed.", webhook=f"http://127.0.0.1:{unused_port()}/hooks/x"
            )

    def test_missing_webhook_url_raises(self):
        # As when SLACK_WEBHOOK_URL is not set.
        with self.assertRaises(requests.exceptions.MissingSchema):
            mattermost.send_webhook_message("Import completed.", webhook=None)


if __name__ == "__main__":
    unittest.main()
