from stats.core.orm.helpers import get_all_data_from_location_mapping_resolved
from stats.core.supabase.helpers import publish_location_mapping_resolved_all
from util.logger import get_logger

logger = get_logger(__name__)


def publish_all_location_mapping_resolved():
    logger.info("Fetching location_mapping_resolved rows for initial Supabase publish.")
    data = get_all_data_from_location_mapping_resolved()
    logger.info(f"Fetched {len(data)} location_mapping_resolved rows.")

    publish_location_mapping_resolved_all(location_data=data)
    logger.info("Initial device data publishing to Supabase completed.")


if __name__ == "__main__":
    publish_all_location_mapping_resolved()
