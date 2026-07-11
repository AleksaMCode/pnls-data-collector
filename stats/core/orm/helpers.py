import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_exponential
from yaspin import yaspin

from stats.core.orm.models import (
    CompanyCaptureSummary,
    CompanyCaptureSummaryByDevice,
    DailyCapturedPerDevice,
    ImportsInfo,
    LocationMappingResolved,
    SsidFirstLastSeen,
    TotalCapturedPerDevice,
)
from util.core.orm.models import Device
from util.logger import get_logger

from . import _session

logger = get_logger(__name__)


def get_all_data_from_company_capture_summary(
    min_percentage: float = 0.001,
) -> list[CompanyCaptureSummary]:
    logger.info(
        f"Getting all data from company capture summary with {min_percentage}% minimum percentage filter."
    )
    # Skip devices marked with Private company for MAC E4F14C. This isn't a real company.
    # TODO: Maybe exclude this from the final results as it affects the total percentage (although not significantly).
    with _session() as db:
        return (
            db.query(CompanyCaptureSummary)
            .filter(CompanyCaptureSummary.percentage >= min_percentage)
            .filter(CompanyCaptureSummary.company != "Private")
            .all()
        )


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=30, max=90),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.ERROR),
)
def get_latest_import_date():
    logger.info("Getting latest import date from the DB.")
    with _session() as db:
        return (
            db.query(ImportsInfo)
            .order_by(desc(ImportsInfo.timestamp))
            .first()
            .timestamp
        )


def get_all_data_from_company_capture_summary_by_device(
    device: Device, min_percentage: float = 0.001, limit: int = 20
) -> list[CompanyCaptureSummaryByDevice]:
    logger.info(
        f"Getting top 20 company capture summary data for {device.value} with {min_percentage}% minimum percentage filter."
    )
    with _session() as db:
        return (
            db.query(CompanyCaptureSummaryByDevice)
            .filter(CompanyCaptureSummaryByDevice.device == device.value)
            .filter(CompanyCaptureSummaryByDevice.percentage >= min_percentage)
            .filter(CompanyCaptureSummaryByDevice.company != "Private")
            .order_by(desc(CompanyCaptureSummaryByDevice.total_occurrences))
            .limit(limit)
            .all()
        )


def get_all_data_from_location_mapping_resolved() -> list[LocationMappingResolved]:
    logger.info("Getting all data from location mapping resolved.")
    with _session() as db:
        return db.query(LocationMappingResolved).all()


def get_device_total_captured_data(device: Device) -> TotalCapturedPerDevice:
    logger.info(f"Getting total captured data for device {device.value}.")
    with _session() as db:
        return (
            db.query(TotalCapturedPerDevice)
            .filter(TotalCapturedPerDevice.device == device.value)
            .one_or_none()
        )


@yaspin(text="Getting all daily total stats from DB...")
def get_daily_totals_all_devices(start_date: date | None = None):
    with _session() as db:
        query = (
            db.query(
                DailyCapturedPerDevice.date.label("date"),
                func.sum(DailyCapturedPerDevice.ssid).label("ssid_count"),
                func.sum(DailyCapturedPerDevice.mac).label("mac_count"),
                func.sum(DailyCapturedPerDevice.probe_request).label("probes_count"),
            )
            .group_by(DailyCapturedPerDevice.date)
            .order_by(DailyCapturedPerDevice.date)
        )
        if start_date is not None:
            query = query.filter(DailyCapturedPerDevice.date >= start_date)
        return query.all()


def get_all_data_from_daily_captured_stats_per_device() -> list[DailyCapturedPerDevice]:
    logger.info("Getting all data from daily captured stats per device.")
    with _session() as db:
        return db.query(DailyCapturedPerDevice).all()


def get_data_from_daily_captured_stats_per_device_between_dates(
    start_date: date, end_date: date
) -> list[DailyCapturedPerDevice]:
    logger.info(
        f"Getting daily captured stats per device between {start_date} and {end_date}."
    )
    with _session() as db:
        return (
            db.query(DailyCapturedPerDevice)
            .filter(DailyCapturedPerDevice.date >= start_date)
            .filter(DailyCapturedPerDevice.date <= end_date)
            .all()
        )


def get_today_data_from_daily_captured_stats_per_device(
    tz: str = "Europe/Paris",
    import_date: date | None = None,
) -> list[DailyCapturedPerDevice]:
    target_date = import_date or datetime.now(ZoneInfo(tz)).date()
    logger.info(
        f"Getting all data from daily captured stats per device for {target_date}."
    )
    with _session() as db:
        return (
            db.query(DailyCapturedPerDevice)
            .filter(DailyCapturedPerDevice.date == target_date)
            .all()
        )


def get_all_data_from_ssid_first_last_seen(
    updated_from: date | None = None,
) -> list[SsidFirstLastSeen]:
    logger.info("Getting all data from ssid first/last seen view.")
    with _session() as db:
        query = db.query(SsidFirstLastSeen)
        if updated_from is not None:
            query = query.filter(SsidFirstLastSeen.last_seen <= updated_from)
        return query.all()
