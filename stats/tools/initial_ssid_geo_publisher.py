from stats.core.supabase.helpers import publish_ssid_geo
from util.logger import get_logger

logger = get_logger(__name__)


def publish_all_ssid_geo():
    """
    Publishes every reduced SSID geolocation to Supabase, replacing already published values.

    Run it once after the `geo` columns are added to `ssid_stats`, or to republish
    after a change to the published format. The daily `POST /stats` step never overwrites.
    """
    logger.info("Starting initial ssid geolocation publish to Supabase.")
    publish_ssid_geo(overwrite=True)
    logger.info("Initial ssid geolocation publishing to Supabase completed.")


if __name__ == "__main__":
    publish_all_ssid_geo()
