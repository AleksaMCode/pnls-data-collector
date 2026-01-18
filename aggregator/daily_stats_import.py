from aggregator.core.orm.helpers import (
    get_all_data_from_daily_captured_stats_per_device,
)
from aggregator.firebase import delete_stats, publish_daily_stats_data


def publish_all_data():
    data = get_all_data_from_daily_captured_stats_per_device()
    publish_daily_stats_data(data)


if __name__ == "__main__":
    # To be used for bulk import
    publish_all_data()
