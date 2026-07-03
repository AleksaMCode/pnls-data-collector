import logging
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from yaspin import yaspin

from aggregator import settings, util
from util.core.orm.models import Device
from util.logger import get_logger

from ...settings import TIMEZONE
from ...util import util
from ...util.util import mac_to_oui_candidates
from . import _session
from .models import (
    IEEE_PRIORITY,
    MAC,
    SSID,
    CapturedInfo,
    CompanyCaptureSummary,
    CompanyCaptureSummaryByDevice,
    Country,
    DailyCapturedPerDevice,
    IEEEMacOuiView,
    IEEERegistry,
    ImportsInfo,
    ImportsWorkflow,
    LocationMapping,
    LocationMappingResolved,
    TotalCapturedPerDevice,
    WorkflowStatus,
)

logger = get_logger(__name__)


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


def get_country_id_with_alpha2(alpha2):
    # logger.info("Getting country ID from the DB.")
    with _session() as db:
        return db.query(Country).filter_by(alpha2=alpha2).one_or_none()


def get_total_captured_info_count():
    logger.info("Getting total captured info count from the DB.")
    with _session() as db:
        return db.query(func.sum(ImportsInfo.captured)).scalar()


def get_total_captured_mac_count():
    logger.info("Getting total captured mac count from the DB.")
    with _session() as db:
        return db.query(func.count(MAC.id)).scalar()


def get_total_captured_ssid_count():
    logger.info("Getting total captured ssid count from the DB.")
    with _session() as db:
        return db.query(func.count(SSID.id)).scalar()


def get_all_data_from_daily_captured_stats_per_device() -> list[DailyCapturedPerDevice]:
    logger.info("Getting all data from daily captured stats per device.")
    with _session() as db:
        return db.query(DailyCapturedPerDevice).all()


def get_today_data_from_daily_captured_stats_per_device(
    tz="Europe/Paris",
) -> list[DailyCapturedPerDevice]:
    logger.info("Getting all data from daily captured stats per device for today.")
    today = datetime.now(ZoneInfo(tz)).date()
    with _session() as db:
        return (
            db.query(DailyCapturedPerDevice)
            .filter(DailyCapturedPerDevice.date == today)
            .all()
        )


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


def get_device_total_captured_data(device: Device) -> TotalCapturedPerDevice:
    logger.info(f"Getting total captured data for device {device.value}.")
    with _session() as db:
        return (
            db.query(TotalCapturedPerDevice)
            .filter(TotalCapturedPerDevice.device == device.value)
            .one_or_none()
        )


def resolve_oui(session, mac: MAC):
    if mac.oui or not mac.uaa:
        return

    candidates = mac_to_oui_candidates(mac.mac)

    for registry in IEEE_PRIORITY:
        assignment = candidates[registry]

        # Build base query using a Materialized View
        query = session.query(IEEEMacOuiView).filter(
            IEEEMacOuiView.registry == registry.value,
            IEEEMacOuiView.assignment == assignment,
        )

        # CERN MA-L workaround (duplicate assignment issue)
        if registry == IEEERegistry.MA_L and assignment == "080030":
            # mac_obj.oui = 37604  # ID for CERN MA-L with 080030
            query = query.filter(IEEEMacOuiView.org == "CERN")

        # IEEE data can contain duplicates → use first()
        # See: https://stackoverflow.com/questions/61213303/how-should-i-handle-duplicate-mac-assignment-in-the-ieee-oui-ma-l-data-file
        oui = query.first()

        if oui:
            mac.oui = oui.id
            return

    mac.oui = None


def create_import_workflow() -> UUID | None:
    with _session() as db:
        workflow = ImportsWorkflow(status=WorkflowStatus.STARTED)
        db.add(workflow)
        try:
            db.commit()
            db.refresh(workflow)
            return workflow.id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to start import workflow - {str(e)}")
            return None


def set_import_workflow_status(workflow_id: UUID, status: WorkflowStatus):
    with _session() as db:
        try:
            workflow = db.query(ImportsWorkflow).filter_by(id=workflow_id).one_or_none()
            if not workflow:
                logger.warning(f"Import workflow {workflow_id} not found.")
                return
            workflow.status = status
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to set import workflow status to {status.value} - {str(e)}"
            )


@yaspin(text="Importing data from Firebase to local database...")
def import_data(
    data,
    firebase_import: bool = True,
    manual_import_date: date = None,
    workflow_id: UUID | None = None,
) -> int:
    """
    Imports data from Firebase to local database.
    Returns count of new Probe Requests imported from Firebase.
    """
    logger.info("Starting import of data from Firebase to local database.")
    with _session() as db:
        try:
            # Cache existing SSIDs and MACs for fast lookup
            ssid_map = {s.ssid: s.id for s in db.query(SSID).all()}
            mac_map = {m.mac: m.id for m in db.query(MAC).all()}

            captured_records = []
            for record in tqdm(data, desc="Importing records", unit="record"):
                device_name = record.get("device")
                ssid_str = util.clean_string(record.get("ssid"))
                mac_str = record.get("mac")
                channel = int(record.get("channel")) or 10

                if mac_str in settings.MAC_FILTER:
                    continue

                timestamp_str = record.get("timestamp")

                if not ssid_str or not mac_str or not timestamp_str:
                    continue

                ts = datetime.strptime(timestamp_str, settings.TIMESTAMP_FORMAT)

                ssid_id = ssid_map.get(ssid_str)
                if not ssid_id:
                    ssid_obj = SSID(ssid=ssid_str)
                    db.add(ssid_obj)
                    db.flush()
                    ssid_map[ssid_str] = ssid_obj.id
                    ssid_id = ssid_obj.id

                mac_id = mac_map.get(mac_str)
                if not mac_id:
                    mac_obj = MAC(mac=mac_str)
                    # Add MAC OUI - explicit call `resolve_oui()`
                    # (this isn't need if event has been imported in the caller)
                    resolve_oui(db, mac_obj)
                    db.add(mac_obj)
                    db.flush()
                    mac_map[mac_str] = mac_obj.id
                    mac_id = mac_obj.id

                mapping = (
                    db.query(LocationMapping).filter_by(device=device_name).first()
                )
                if not mapping:
                    logger.warning(
                        f"No location mapping found for device {device_name}, skipping record."
                    )
                    continue

                location_id = mapping.location_id
                captured_records.append(
                    CapturedInfo(
                        ssid=ssid_id,
                        mac=mac_id,
                        location=location_id,
                        channel=channel,
                        timestamp=ts,
                    )
                )

            # There is still a very small change of a race condition, but this fix is good enough for #198
            today = datetime.now(ZoneInfo(TIMEZONE)).date()
            latest_import_date = get_latest_import_date()
            if latest_import_date == today:
                logger.info(
                    f"Skipping import for {today}: import already occurred today."
                )
                raise Exception("Import already occurred today.")
            if captured_records:
                db.add_all(captured_records)
                # Only update stats when importing from Firebase.
                # For import of local data manually update stats.
                # TODO Maybe fix this (automate stats update) in the future #techdebt
                if firebase_import:
                    if manual_import_date:
                        db.add(
                            ImportsInfo(
                                captured=len(captured_records),
                                timestamp=manual_import_date,
                                workflow_id=workflow_id,
                            )
                        )
                    else:
                        db.add(
                            ImportsInfo(
                                captured=len(captured_records), workflow_id=workflow_id
                            )
                        )

            db.commit()
            logger.info(f"Imported {len(captured_records)} new captured records.")
            return len(captured_records)
        except Exception as e:
            db.rollback()
            logger.error(f"Error occurred during data import - {str(e)}")
            return 0
