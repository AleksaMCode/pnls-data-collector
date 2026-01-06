import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials

from aggregator.core.orm.helpers import get_latest_import_date, import_data
from aggregator.mattermost import publish_to_channel
from util.logger import get_logger
from util.util import is_after_six

from .firebase import fetch_all_data, fetch_data, publish_stats_data
from .settings import FIREBASE_CREDENTIALS, FIREBASE_DB_URL, TIMEZONE

firebase_admin.initialize_app(
    credentials.Certificate(FIREBASE_CREDENTIALS),
    {"databaseURL": FIREBASE_DB_URL},
)

logger = get_logger(__name__)

IMPORT_DATE_START = get_latest_import_date() + timedelta(days=1)

# If server doesn't run for multiple days, there is import for more than one day.
IMPORT_DATES = [
    IMPORT_DATE_START + timedelta(days=n)
    for n in range(
        (datetime.now(ZoneInfo(TIMEZONE)).date() - IMPORT_DATE_START).days + 1
    )
]


def transfer_all_data_from_firebase_to_db():
    """
    Imports data to local DB only for the next import date based on the information about import in the DB.
    """
    data = fetch_all_data(IMPORT_DATE_START)
    import_data(data)


def transfer_data(import_date: date, manual_import=False):
    """
    Transfer data for `import_date` date.
    """
    data = fetch_data(import_date)
    count = import_data(
        data,
        firebase_import=True,
        manual_import_date=import_date if manual_import else None,
    )
    stats = publish_stats_data()
    # Publish message to Mattermost.
    try:
        publish_to_channel(stats, count, import_date if manual_import else None)
    except Exception as e:
        logger.error(f"Publishing stats data to Mattermost failed: {str(e)}")


def transfer_data_all():
    """
    Transfer data for days after latest_import.
    """
    if not len(IMPORT_DATES):
        logger.info("There is nothing to import.")
        return

    for import_date in IMPORT_DATES:
        logger.info(f"Transfer data from {import_date}.")
        transfer_data(import_date)


if __name__ == "__main__":
    # Exit if it is still working hours.
    # This was added to fix power outage issue. See #59
    if not is_after_six(TIMEZONE):
        logger.info("Aggregator can only run after 18:00.")
        sys.exit(0)
    else:
        logger.info("Starting aggregator.")
        transfer_data_all()
