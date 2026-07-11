from sqlalchemy import MetaData, Table, insert, select, update
from sqlalchemy.exc import IntegrityError
from yaspin import yaspin

from stats.core.orm.helpers import (
    get_daily_totals_all_devices,
    get_all_data_from_location_mapping_resolved,
    get_device_total_captured_data,
)
from stats.core.supabase.models import (
    DailyImportsMac,
    DailyImportsProbes,
    DailyImportsSsid,
)
from util.core.orm.models import Device
from util.logger import get_logger

from . import _session

logger = get_logger(__name__)


def _publish_daily_metric_all(
    model,
    metric_key: str,
    daily_totals: list | None = None,
    skip_update: bool = True,
):
    data = daily_totals if daily_totals is not None else get_daily_totals_all_devices()

    with _session() as db:
        try:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0
            for row in data:
                metric_value = getattr(row, metric_key, None)
                if metric_value is None:
                    skipped_count += 1
                    continue

                payload = {"date": row.date, "count": int(metric_value)}
                try:
                    with db.begin_nested():
                        db.add(model(**payload))
                    inserted_count += 1
                except IntegrityError:
                    if skip_update:
                        logger.info(
                            f"Skipping update for date '{payload['date']}' in table "
                            f"'{model.__tablename__}' because skip_update=True."
                        )
                        skipped_count += 1
                        continue

                    # Existing date row: update the count instead.
                    with db.begin_nested():
                        existing = (
                            db.query(model)
                            .filter(model.date == payload["date"])
                            .one_or_none()
                        )
                        if existing:
                            existing.count = payload["count"]
                            updated_count += 1
                        else:
                            skipped_count += 1
                except Exception as row_error:
                    skipped_count += 1
                    logger.warning(
                        f"Skipping row for date '{payload['date']}' in table '{model.__tablename__}'"
                        f" due to error: {str(row_error)}"
                    )
                    continue

            db.commit()
            logger.info(
                f"Published daily metric to '{model.__tablename__}'"
                f" (inserted={inserted_count}, updated={updated_count}, skipped={skipped_count})."
            )
        except Exception as e:
            db.rollback()
            logger.error(
                f"Publishing daily metric '{metric_key}' to table '{model.__tablename__}' failed: {str(e)}"
            )
            raise


@yaspin(text="Publishing all daily SSID totals to Supabase...")
def publish_ssid_all(daily_totals: list | None = None):
    _publish_daily_metric_all(
        model=DailyImportsSsid,
        metric_key="ssid_count",
        daily_totals=daily_totals,
    )


@yaspin(text="Publishing all daily MAC totals to Supabase...")
def public_mac_all(daily_totals: list | None = None):
    _publish_daily_metric_all(
        model=DailyImportsMac,
        metric_key="mac_count",
        daily_totals=daily_totals,
    )


@yaspin(text="Publishing all daily probe totals to Supabase...")
def public_probes_all(daily_totals: list | None = None):
    _publish_daily_metric_all(
        model=DailyImportsProbes,
        metric_key="probes_count",
        daily_totals=daily_totals,
    )