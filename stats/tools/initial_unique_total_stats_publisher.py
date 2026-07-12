from stats.core.orm.helpers import get_latest_import_date, get_unique_totals_snapshot
from stats.core.supabase.helpers import publish_unique_total_stats
from util.logger import get_logger

logger = get_logger(__name__)


def publish_initial_unique_total_stats():
    logger.info("Fetching unique totals snapshot from local DB.")
    snapshot = get_unique_totals_snapshot()
    logger.info(f"Fetched unique totals snapshot: {snapshot}")

    target_date = get_latest_import_date()
    logger.info(f"Publishing unique totals snapshot for date: {target_date}")
    publish_unique_total_stats(target_date=target_date, totals_data=snapshot)
    logger.info("Initial unique totals snapshot publishing to Supabase completed.")


if __name__ == "__main__":
    publish_initial_unique_total_stats()
