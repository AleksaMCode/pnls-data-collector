from datetime import date
from datetime import date as dt_date
from warnings import deprecated

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm
from yaspin import yaspin

from stats.core.orm.helpers import (
    get_all_data_from_company_capture_summary,
    get_all_data_from_company_capture_summary_by_device,
    get_all_data_from_daily_captured_stats_per_device,
    get_all_data_from_location_mapping_resolved,
    get_all_data_from_ssid_first_last_seen,
    get_daily_totals_all_devices,
    get_today_data_from_daily_captured_stats_per_device,
)
from stats.core.supabase.models import (
    DailyImportsMac,
    DailyImportsProbes,
    DailyImportsSsid,
)
from stats.core.supabase.models import Device as DeviceModel
from stats.core.supabase.models import (
    DeviceDailyImports,
    DeviceManufacturerStats,
    ManufacturerStats,
    SsidStats,
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


@yaspin(text="Publishing all location mapping data about devices to Supabase...")
def publish_location_mapping_resolved_all(
    location_data: list | None = None,
    skip_update: bool = False,
):
    data = (
        location_data
        if location_data is not None
        else get_all_data_from_location_mapping_resolved()
    )

    with _session() as db:
        try:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0
            for row in data:
                payload = {
                    "device": row.device,
                    "location": row.location,
                    "coordinates": row.coordinates,
                }

                try:
                    with db.begin_nested():
                        db.add(DeviceModel(**payload))
                    inserted_count += 1
                except IntegrityError:
                    if skip_update:
                        logger.info(
                            f"Skipping update for device '{payload['device']}' in table "
                            f"'{DeviceModel.__tablename__}' because skip_update=True."
                        )
                        skipped_count += 1
                        continue

                    with db.begin_nested():
                        existing = (
                            db.query(DeviceModel)
                            .filter(DeviceModel.device == payload["device"])
                            .one_or_none()
                        )
                        if existing:
                            existing.location = payload["location"]
                            existing.coordinates = payload["coordinates"]
                            updated_count += 1
                        else:
                            skipped_count += 1
                except Exception as row_error:
                    skipped_count += 1
                    logger.warning(
                        "Skipping location mapping row for device "
                        f"'{payload['device']}' due to error: {str(row_error)}"
                    )
                    continue

            db.commit()
            logger.info(
                "Published location mapping rows to "
                f"'{DeviceModel.__tablename__}' "
                f"(inserted={inserted_count}, updated={updated_count}, skipped={skipped_count})."
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Publishing location mapping rows to "
                f"'{DeviceModel.__tablename__}' failed: {str(e)}"
            )
            raise


@yaspin(text="Publishing device daily imports to Supabase...")
def publish_device_daily_imports_all(
    device_daily_data: list | None = None,
    skip_update: bool = True,
):
    data = (
        device_daily_data
        if device_daily_data is not None
        else get_all_data_from_daily_captured_stats_per_device()
    )

    with _session() as db:
        try:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0
            for row in data:
                payload = {
                    "device_id": row.device,
                    "ssid": int(row.ssid),
                    "mac": int(row.mac),
                    "probes": int(row.probe_request),
                    "date": row.date,
                }

                try:
                    with db.begin_nested():
                        db.add(DeviceDailyImports(**payload))
                    inserted_count += 1
                except IntegrityError:
                    if skip_update:
                        logger.info(
                            "Skipping update for "
                            f"device '{payload['device_id']}' on '{payload['date']}' in table "
                            f"'{DeviceDailyImports.__tablename__}' because skip_update=True."
                        )
                        skipped_count += 1
                        continue

                    with db.begin_nested():
                        existing = (
                            db.query(DeviceDailyImports)
                            .filter(
                                DeviceDailyImports.device_id == payload["device_id"],
                                DeviceDailyImports.date == payload["date"],
                            )
                            .one_or_none()
                        )
                        if existing:
                            existing.ssid = payload["ssid"]
                            existing.mac = payload["mac"]
                            existing.probes = payload["probes"]
                            updated_count += 1
                        else:
                            skipped_count += 1
                except Exception as row_error:
                    skipped_count += 1
                    logger.warning(
                        "Skipping device daily import row for device "
                        f"'{payload['device_id']}' and date '{payload['date']}' "
                        f"due to error: {str(row_error)}"
                    )
                    continue

            db.commit()
            logger.info(
                "Published device daily import rows to "
                f"'{DeviceDailyImports.__tablename__}' "
                f"(inserted={inserted_count}, updated={updated_count}, skipped={skipped_count})."
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Publishing device daily import rows to "
                f"'{DeviceDailyImports.__tablename__}' failed: {str(e)}"
            )
            raise


@yaspin(text="Publishing device manufacturer stats to Supabase...")
def publish_device_manufacturer_stats_all(target_date: dt_date | None = None):
    effective_date = target_date or dt_date.today()

    with _session() as db:
        try:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0

            for device in Device:
                manufacturer_rows = get_all_data_from_company_capture_summary_by_device(
                    device
                )
                manufacturer_data = [
                    {
                        "company": row.company,
                        "country": row.country,
                        "country_alpha3": row.country_alpha3,
                        "total_occurrences": row.total_occurrences,
                        "percentage": float(row.percentage),
                    }
                    for row in manufacturer_rows
                ]

                payload = {
                    "device_id": device.value,
                    "manufacturer_data": manufacturer_data,
                    "date": effective_date,
                }

                try:
                    with db.begin_nested():
                        db.add(DeviceManufacturerStats(**payload))
                    inserted_count += 1
                except IntegrityError:
                    logger.info(
                        "Skipping device manufacturer stats import for device "
                        f"'{payload['device_id']}' on '{payload['date']}' because it already exists."
                    )
                    skipped_count += 1
                except Exception as row_error:
                    skipped_count += 1
                    logger.warning(
                        "Skipping device manufacturer stats row for device "
                        f"'{payload['device_id']}' and date '{payload['date']}' "
                        f"due to error: {str(row_error)}"
                    )
                    continue

            db.commit()
            logger.info(
                "Published device manufacturer stats rows to "
                f"'{DeviceManufacturerStats.__tablename__}' "
                f"(inserted={inserted_count}, updated={updated_count}, skipped={skipped_count})."
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Publishing device manufacturer stats rows to "
                f"'{DeviceManufacturerStats.__tablename__}' failed: {str(e)}"
            )
            raise


@yaspin(text="Publishing manufacturer stats to Supabase...")
def publish_manufacturer_stats_all(summary_data: list | None = None):
    data = (
        summary_data
        if summary_data is not None
        else get_all_data_from_company_capture_summary()
    )

    with _session() as db:
        try:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0

            for row in data:
                payload = {
                    "company": row.company,
                    "country": row.country,
                    "country_alpha3": row.country_alpha3,
                    "total_occurrences": int(row.total_occurrences),
                    "percentage": float(row.percentage),
                }

                try:
                    existing_query = db.query(ManufacturerStats).filter(
                        ManufacturerStats.company == payload["company"]
                    )
                    if payload["country"] is None:
                        existing_query = existing_query.filter(
                            ManufacturerStats.country.is_(None)
                        )
                    else:
                        existing_query = existing_query.filter(
                            ManufacturerStats.country == payload["country"]
                        )

                    if payload["country_alpha3"] is None:
                        existing_query = existing_query.filter(
                            ManufacturerStats.country_alpha3.is_(None)
                        )
                    else:
                        existing_query = existing_query.filter(
                            ManufacturerStats.country_alpha3
                            == payload["country_alpha3"]
                        )

                    existing = existing_query.order_by(
                        ManufacturerStats.id.desc()
                    ).first()
                    if existing:
                        existing.total_occurrences = payload["total_occurrences"]
                        existing.percentage = payload["percentage"]
                        updated_count += 1
                    else:
                        db.add(ManufacturerStats(**payload))
                        inserted_count += 1
                except Exception as row_error:
                    skipped_count += 1
                    logger.warning(
                        "Skipping manufacturer stats row for company "
                        f"'{payload['company']}' due to error: {str(row_error)}"
                    )
                    continue

            db.commit()
            logger.info(
                "Published manufacturer stats rows to "
                f"'{ManufacturerStats.__tablename__}' "
                f"(inserted={inserted_count}, updated={updated_count}, skipped={skipped_count})."
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Publishing manufacturer stats rows to "
                f"'{ManufacturerStats.__tablename__}' failed: {str(e)}"
            )
            raise


@deprecated(
    "Don't use this as it is too slow for updates. Use `publish_ssid_stats_all_batched` instead."
)
@yaspin(text="Publishing ssid stats to Supabase...")
def publish_ssid_stats_all(
    ssid_stats_data: list | None = None,
    updated_from: date | None = None,
):
    data = (
        ssid_stats_data
        if ssid_stats_data is not None
        else get_all_data_from_ssid_first_last_seen(updated_from=updated_from)
    )

    with _session() as db:
        try:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0

            for row in tqdm(data, desc="Publishing ssid stats", unit="row"):
                payload = {
                    "ssid": row.ssid,
                    "seen_count": int(row.seen_count),
                    "first_seen": row.first_seen,
                    "last_seen": row.last_seen,
                }

                try:
                    with db.begin_nested():
                        db.add(SsidStats(**payload))
                    inserted_count += 1
                except IntegrityError:
                    with db.begin_nested():
                        existing = (
                            db.query(SsidStats)
                            .filter(SsidStats.ssid == payload["ssid"])
                            .one_or_none()
                        )
                        if existing:
                            existing.seen_count = payload["seen_count"]
                            if (
                                existing.first_seen is None
                                or payload["first_seen"] < existing.first_seen
                            ):
                                existing.first_seen = payload["first_seen"]
                            if (
                                existing.last_seen is None
                                or payload["last_seen"] > existing.last_seen
                            ):
                                existing.last_seen = payload["last_seen"]
                            updated_count += 1
                        else:
                            skipped_count += 1
                except Exception as row_error:
                    skipped_count += 1
                    logger.warning(
                        "Skipping ssid stats row for ssid "
                        f"'{payload['ssid']}' due to error: {str(row_error)}"
                    )
                    continue

            db.commit()
            logger.info(
                "Published ssid stats rows to "
                f"'{SsidStats.__tablename__}' "
                f"(inserted={inserted_count}, updated={updated_count}, skipped={skipped_count})."
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Publishing ssid stats rows to "
                f"'{SsidStats.__tablename__}' failed: {str(e)}"
            )
            raise


@yaspin(text="Publishing ssid stats to Supabase in batches...")
def publish_ssid_stats_all_batched(
    ssid_stats_data: list | None = None,
    updated_from: date | None = None,
    batch_size: int = 1000,
):
    data = (
        ssid_stats_data
        if ssid_stats_data is not None
        else get_all_data_from_ssid_first_last_seen(updated_from=updated_from)
    )
    rows = [
        {
            "ssid": row.ssid,
            "seen_count": int(row.seen_count),
            "first_seen": row.first_seen,
            "last_seen": row.last_seen,
        }
        for row in data
    ]

    if not rows:
        logger.info("No ssid stats rows to publish in batched mode.")
        return

    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    with _session() as db:
        try:
            processed_count = 0
            for i in tqdm(
                range(0, len(rows), batch_size),
                desc="Publishing ssid stats (batches)",
                unit="batch",
            ):
                chunk = rows[i : i + batch_size]

                stmt = insert(SsidStats).values(chunk)
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=[SsidStats.ssid],
                    set_={
                        "seen_count": stmt.excluded.seen_count,
                        "first_seen": func.least(
                            SsidStats.first_seen, stmt.excluded.first_seen
                        ),
                        "last_seen": func.greatest(
                            SsidStats.last_seen, stmt.excluded.last_seen
                        ),
                    },
                )
                db.execute(upsert_stmt)
                processed_count += len(chunk)

            db.commit()
            logger.info(
                "Published ssid stats rows in batches to "
                f"'{SsidStats.__tablename__}' "
                f"(processed={processed_count}, batch_size={batch_size})."
            )
        except Exception as e:
            db.rollback()
            logger.error(
                "Publishing ssid stats rows in batches to "
                f"'{SsidStats.__tablename__}' failed: {str(e)}"
            )
            raise


@yaspin(text="Publishing today's device daily imports to Supabase...")
def publish_device_daily_imports_today(
    tz: str = "Europe/Paris", import_date: date | None = None
):
    today_rows = get_today_data_from_daily_captured_stats_per_device(
        tz=tz,
        import_date=import_date,
    )
    publish_device_daily_imports_all(device_daily_data=today_rows)
