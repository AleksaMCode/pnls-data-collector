from stats.core.orm.helpers import get_daily_totals_all_devices
from stats.core.supabase.helpers import (
    public_mac_all,
    public_probes_all,
    publish_ssid_all,
)
from util.logger import get_logger

logger = get_logger(__name__)


def publish_all_daily_imports():
    logger.info("Fetching all daily totals for initial Supabase publishing.")
    daily_totals = get_daily_totals_all_devices()
    logger.info(f"Fetched {len(daily_totals)} daily totals rows.")

    publish_ssid_all(daily_totals=daily_totals)
    public_mac_all(daily_totals=daily_totals)
    public_probes_all(daily_totals=daily_totals)

    logger.info("Initial daily imports publishing to Supabase completed.")


if __name__ == "__main__":
    publish_all_daily_imports()
