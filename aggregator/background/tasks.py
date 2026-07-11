import json
from datetime import date
from uuid import UUID

from aggregator.background.celery import celery
from aggregator.core.firebase.helpers import (
    fetch_data,
)

# This import is needed in order for listener to work.
from aggregator.core.orm import event  # noqa: F401
from aggregator.core.orm.helpers import (
    get_totals,
    import_data,
    set_import_workflow_status,
)
from aggregator.core.orm.models import WorkflowStatus
from aggregator.core.redis.helpers import set_key_value
from aggregator.settings import WORKFLOW_FINAL_STATUS_TTL_SECONDS
from aggregator.util.util import publish_message_to_channel, publish_to_channel
from util.logger import get_logger

logger = get_logger(__name__)


def transfer_data(import_date: date, workflow_id: UUID):
    data = fetch_data(import_date)
    count = import_data(
        data,
        firebase_import=True,
        manual_import_date=import_date,
        workflow_id=workflow_id,
    )
    stats = get_totals()

    try:
        publish_to_channel(stats, count, import_date)
    except Exception as e:
        logger.error(f"Publishing stats data to Mattermost failed: {str(e)}")


def transfer_data_all(import_dates: list[date], workflow_id: UUID):
    if not import_dates:
        logger.info("There is nothing to import.")
        return

    for import_date in import_dates:
        msg = f"Transfer data from {import_date} workflow started."
        publish_message_to_channel(msg)
        logger.info(msg)
        transfer_data(import_date, workflow_id)

    logger.info("Data aggregation workflow completed.")


@celery.task(name="aggregator.import_workflow")
def import_workflow_task(workflow_id: str, import_dates: list[str]):
    workflow_uuid = UUID(workflow_id)
    parsed_import_dates = [date.fromisoformat(d) for d in import_dates]

    try:
        transfer_data_all(parsed_import_dates, workflow_uuid)
        set_import_workflow_status(workflow_uuid, WorkflowStatus.COMPLETED)
        set_key_value(
            workflow_id,
            json.dumps({"status": WorkflowStatus.COMPLETED.value}),
            ttl=WORKFLOW_FINAL_STATUS_TTL_SECONDS,
        )
        return {"workflow_id": workflow_id, "status": WorkflowStatus.COMPLETED.value}
    except Exception:
        set_import_workflow_status(workflow_uuid, WorkflowStatus.FAILED)
        set_key_value(
            workflow_id,
            json.dumps({"status": WorkflowStatus.FAILED.value}),
            ttl=WORKFLOW_FINAL_STATUS_TTL_SECONDS,
        )
        raise
