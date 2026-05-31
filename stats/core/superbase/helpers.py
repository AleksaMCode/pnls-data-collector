from yaspin import yaspin

from stats.core.orm.helpers import get_all_data_from_location_mapping_resolved
from util.logger import get_logger

from . import _session

logger = get_logger(__name__)

@yaspin(text="Publishing device location data to Superbase...")
def publish_devices_data():
    device_data = get_all_data_from_location_mapping_resolved()

    try:
        for device_info in device_data:
            # Write publishing to Superbase
        logger.info("Published devices data to Superbase.")
    except Exception as e:
        logger.error(f"Publishing devices data to Superbase failed: {str(e)}")
