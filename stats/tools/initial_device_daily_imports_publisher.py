from stats.core.orm.helpers import get_all_data_from_daily_captured_stats_per_device
from stats.core.supabase.helpers import publish_device_daily_imports_all
from util.logger import get_logger

logger = get_logger(__name__)


def publish_all_device_daily_imports():
    logger.info("Fetching device daily imports from local DB for initial Supabase publish.")
    data = get_all_data_from_daily_captured_stats_per_device()
    logger.info(f"Fetched {len(data)} device daily import rows.")

    publish_device_daily_imports_all(device_daily_data=data)
    logger.info("Initial device daily imports publishing to Supabase completed.")


if __name__ == "__main__":
    publish_all_device_daily_imports()
