import csv
import os
from datetime import datetime
from pathlib import Path

from stats.core.orm.helpers import get_all_data_from_mac_first_last_seen
from stats.util.util import hash_mac_hmac_sha256
from util.logger import get_logger

logger = get_logger(__name__)


def _format_datetime_for_csv(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def export_mac_stats_to_csv(output_path: str = "mac_stats_export.csv"):
    pepper = os.getenv("MAC_HASH_PEPPER")
    if not pepper:
        raise RuntimeError("MAC_HASH_PEPPER is required to export MAC stats CSV.")

    logger.info("Fetching MAC stats from local DB for CSV export.")
    data = get_all_data_from_mac_first_last_seen()
    logger.info(f"Fetched {len(data)} MAC stats rows.")

    rows = [
        {
            "mac": hash_mac_hmac_sha256(row.mac, pepper),
            "seen_count": int(row.seen_count),
            "first_seen": row.first_seen,
            "last_seen": row.last_seen,
        }
        for row in data
    ]

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["mac", "seen_count", "first_seen", "last_seen"]
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Exported {len(rows)} MAC stats rows to CSV: {output_file.resolve()}")


if __name__ == "__main__":
    export_mac_stats_to_csv()
