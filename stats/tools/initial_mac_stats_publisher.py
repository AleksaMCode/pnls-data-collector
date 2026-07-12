from stats.core.orm.helpers import get_all_data_from_mac_first_last_seen
from stats.core.supabase.helpers import publish_mac_stats_all_batched
from util.logger import get_logger

logger = get_logger(__name__)


def publish_all_mac_stats():
    logger.info("Fetching mac stats from local DB for initial Supabase publish.")
    data = get_all_data_from_mac_first_last_seen()
    logger.info(f"Fetched {len(data)} mac stats rows.")

    publish_mac_stats_all_batched(mac_stats_data=data)
    logger.info("Initial mac stats publishing to Supabase completed.")


if __name__ == "__main__":
    publish_all_mac_stats()
