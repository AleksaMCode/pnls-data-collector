import json
import os
from enum import Enum

# Fix for pipeline. See #38
if os.getenv("ENV") != "test":
    import requests

from . import logger


class MattermostBot(str, Enum):
    AGGREGATOR = "Aggregator"
    HOUSEKEEPING = "Housekeeping"


BOT_ICON_FILENAME_MAP = {
    # From https://www.flaticon.com/free-icon/aggregation_6146592
    MattermostBot.AGGREGATOR: "aggregator.png",
    # From https://www.flaticon.com/free-icon/cleaning_14261556
    MattermostBot.HOUSEKEEPING: "housekeeping.png",
}

BOT_ICON_BASE_URL = (
    "https://raw.githubusercontent.com/"
    "AleksaMCode/pnls-data-collector/master/resources/bot_icons/"
)
BOT_ICON_URL_MAP = {
    bot_name: f"{BOT_ICON_BASE_URL}{filename}"
    for bot_name, filename in BOT_ICON_FILENAME_MAP.items()
}
DEFAULT_ICON_URL = BOT_ICON_URL_MAP[MattermostBot.AGGREGATOR]


def send_webhook_message(
    message: str, *, webhook: str, bot_name: MattermostBot = MattermostBot.AGGREGATOR
):
    """
    Sends a message to a Slack like app (Mattermost) via webhook.
    """
    data = {
        "text": message,
        "username": bot_name.value,
        "icon_url": BOT_ICON_URL_MAP.get(bot_name, DEFAULT_ICON_URL),
    }

    response = requests.post(
        webhook,
        data=json.dumps(data),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    if response.status_code != 200:
        raise ValueError(
            f"Request to Mattermost returned an error {response.status_code}, the response is:\n{response.text}"
        )
    else:
        logger.info("Slack webhook message sent to Mattermost.")
