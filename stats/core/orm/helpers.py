from sqlalchemy import desc

from stats.core.orm.models import CompanyCaptureSummary, CompanyCaptureSummaryByDevice, LocationMappingResolved
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