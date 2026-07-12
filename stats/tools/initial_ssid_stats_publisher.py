from stats.core.orm.helpers import get_all_data_from_ssid_first_last_seen
from stats.core.supabase.helpers import publish_ssid_stats_all_batched
from util.logger import get_logger

logger = get_logger(__name__)


def publish_all_ssid_stats():
    logger.info("Fetching ssid stats from local DB for initial Supabase publish.")
    data = get_all_data_from_ssid_first_last_seen()
    logger.info(f"Fetched {len(data)} ssid stats rows.")

    publish_ssid_stats_all_batched(ssid_stats_data=data)
    logger.info("Initial ssid stats publishing to Supabase completed.")


if __name__ == "__main__":
    publish_all_ssid_stats()
