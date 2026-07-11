from stats.core.supabase.helpers import publish_device_manufacturer_stats_all
from util.logger import get_logger

logger = get_logger(__name__)


def publish_device_manufacturer_stats():
    logger.info("Starting initial device manufacturer stats publishing to Supabase.")
    publish_device_manufacturer_stats_all()
    logger.info("Initial device manufacturer stats publishing to Supabase completed.")


if __name__ == "__main__":
    publish_device_manufacturer_stats()
