import argparse
from datetime import datetime

from aggregator.aggregator import transfer_data
from aggregator.settings import TIMESTAMP_FORMAT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process data for a specific date")
    parser.add_argument(
        "--date",
        required=True,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Date to process in YYYY-MM-DD format",
    )

    args = parser.parse_args()
    date = datetime.strptime(args.date, TIMESTAMP_FORMAT.split(" ")[0]).date()
    transfer_data(date, True)
