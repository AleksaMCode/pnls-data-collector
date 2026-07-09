import argparse
from datetime import date

from aggregator.core.firebase.helpers import publish_daily_stats_data
from aggregator.core.orm.helpers import (
    get_all_data_from_daily_captured_stats_per_device,
    get_data_from_daily_captured_stats_per_device_between_dates,
)


def publish_all_data():
    data = get_all_data_from_daily_captured_stats_per_device()
    publish_daily_stats_data(data)


def publish_data_between_dates(start_date: date, end_date: date):
    data = get_data_from_daily_captured_stats_per_device_between_dates(
        start_date, end_date
    )
    publish_daily_stats_data(data)


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Publish daily captured stats to Firebase either for all dates or "
            "for an inclusive date window."
        )
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Publish all daily stats records.",
    )
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        help="Start date in ISO format (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        help="End date in ISO format (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    if args.all and (args.start_date or args.end_date):
        parser.error("Use either --all or --start-date/--end-date, not both.")

    if args.all:
        return args

    if args.start_date is None or args.end_date is None:
        parser.error("Provide --all or both --start-date and --end-date.")

    if args.start_date > args.end_date:
        parser.error("--start-date cannot be after --end-date.")

    return args


if __name__ == "__main__":
    args = _parse_args()
    if args.all:
        publish_all_data()
    else:
        publish_data_between_dates(args.start_date, args.end_date)
