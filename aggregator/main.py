import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from aggregator.core.firebase.helpers import (
    fetch_all_data,
    fetch_data,
    publish_manufacturers_data,
    publish_sankey_data,
    publish_stats_data,
)

# This import is needed in order for listener to work!! - from aggregator.core.orm import event
from aggregator.core.orm.helpers import (
    create_import_workflow,
    get_latest_import_date,
    import_data,
    set_import_workflow_status,
)
from aggregator.core.orm.models import WorkflowStatus
from aggregator.core.redis.helpers import set_key_value
from aggregator.settings import (
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
    SERVICE_VERSION,
    TIMEZONE,
)
from aggregator.util.util import (
    get_pending_import_dates,
    publish_message_to_channel,
    publish_to_channel,
)
from util.logger import get_logger
from util.util import is_after_six

logger = get_logger(__name__)
WORKFLOW_STATUS_TTL_SECONDS = 120


# If server doesn't run for multiple days, import is done for more than one day.
def transfer_all_data_from_firebase_to_db(workflow_id: UUID | None = None):
    """
    Imports data to local DB only for the next import date based on the information about import in the DB.
    """
    import_date_start = get_latest_import_date() + timedelta(days=1)
    data = fetch_all_data(import_date_start)
    import_data(data, workflow_id=workflow_id)


def transfer_data(
    import_date: date, manual_import=False, workflow_id: UUID | None = None
):
    """
    Transfer data for `import_date` date.
    """
    data = fetch_data(import_date)
    count = import_data(
        data,
        firebase_import=True,
        manual_import_date=import_date if manual_import else None,
        workflow_id=workflow_id,
    )
    stats = publish_stats_data()
    publish_manufacturers_data()
    publish_sankey_data()
    # Publish message to Mattermost.
    try:
        publish_to_channel(stats, count, import_date if manual_import else None)
    except Exception as e:
        logger.error(f"Publishing stats data to Mattermost failed: {str(e)}")


def transfer_data_all(import_dates: list[date], workflow_id: UUID | None = None):
    """
    Transfer data for days after latest_import.
    """
    if not len(import_dates):
        logger.info("There is nothing to import.")
        return

    for import_date in import_dates:
        msg = f"Transfer data from {import_date} workflow started."
        publish_message_to_channel(msg)
        logger.info(msg)
        transfer_data(import_date, workflow_id=workflow_id)
    logger.info("Data aggregation workflow completed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Server starting.")
    yield
    logger.info("Server shutting down.")


app = FastAPI(
    lifespan=lifespan,
    title=SERVICE_NAME,
    description=SERVICE_DESCRIPTION,
    version=SERVICE_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/aggregate")
async def aggregate():
    import_dates = get_pending_import_dates(
        latest_import_date=get_latest_import_date(),
        current_date=datetime.now(ZoneInfo(TIMEZONE)).date(),
    )
    if import_dates and not is_after_six(TIMEZONE):
        logger.info("Aggregator can only run after 18:00.")
        return {"status": "skipped", "message": "Aggregator can only run after 18:00."}

    workflow_id = create_import_workflow()
    if not workflow_id:
        return {"status": "error", "message": "Failed to create import workflow."}

    set_key_value(
        str(workflow_id),
        json.dumps({"status": WorkflowStatus.STARTED.value}),
    )

    logger.info("Starting aggregator.")
    try:
        transfer_data_all(import_dates, workflow_id=workflow_id)
        set_import_workflow_status(workflow_id, WorkflowStatus.COMPLETED)
        set_key_value(
            str(workflow_id),
            json.dumps({"status": WorkflowStatus.COMPLETED.value}),
            ttl=WORKFLOW_STATUS_TTL_SECONDS,
        )
        return {
            "status": "ok",
            "workflow_id": str(workflow_id),
            "message": "Data aggregation workflow completed.",
        }
    except Exception:
        set_import_workflow_status(workflow_id, WorkflowStatus.FAILED)
        set_key_value(
            str(workflow_id),
            json.dumps({"status": WorkflowStatus.FAILED.value}),
            ttl=WORKFLOW_STATUS_TTL_SECONDS,
        )
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_URL"),
        port=int(os.getenv("SERVER_PORT")),
        reload=False,
    )
