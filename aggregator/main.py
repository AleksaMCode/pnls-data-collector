import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware

from aggregator.background.tasks import import_workflow_task

# This import is needed in order for listener to work.
from aggregator.core.orm import event  # noqa: F401
from aggregator.core.orm.helpers import (
    create_import_workflow,
    get_import_workflow_status,
    get_latest_import_date,
)
from aggregator.core.orm.models import WorkflowStatus
from aggregator.core.redis.helpers import get_key_value, set_key_value
from aggregator.settings import (
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
    SERVICE_VERSION,
    TIMEZONE,
)
from aggregator.util.models import AggregateWorkflowStatus
from aggregator.util.util import (
    get_pending_import_dates,
)
from util.logger import get_logger

logger = get_logger(__name__)


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


@app.post("/aggregate", status_code=202)
async def aggregate():
    import_dates = get_pending_import_dates(
        latest_import_date=get_latest_import_date(),
        current_date=datetime.now(ZoneInfo(TIMEZONE)).date(),
    )
    if not import_dates:
        msg = "Aggregator imports are already up to date."
        logger.info(msg)
        return {"status": AggregateWorkflowStatus.SKIPPED.value, "message": msg}

    workflow_id = create_import_workflow()
    if not workflow_id:
        return {
            "status": AggregateWorkflowStatus.ERROR.value,
            "message": "Failed to create import workflow.",
        }

    set_key_value(
        str(workflow_id),
        json.dumps({"status": WorkflowStatus.STARTED.value}),
    )

    import_dates_payload = [d.isoformat() for d in import_dates]
    task = import_workflow_task.delay(str(workflow_id), import_dates_payload)
    logger.info(
        f"Aggregation workflow queued. workflow_id={workflow_id}, task_id={task.id}"
    )
    return {
        "status": AggregateWorkflowStatus.ACCEPTED.value,
        "workflow_id": str(workflow_id),
        "task_id": task.id,
        "message": "Data aggregation workflow queued.",
    }


@app.get("/aggregate/{workflow_id}")
async def get_aggregate_workflow_status(workflow_id: str):
    status_payload = get_key_value(workflow_id)
    if status_payload is not None:
        try:
            payload = json.loads(status_payload)
            status = payload["status"]
            return {"workflow_id": workflow_id, "status": status}
        except (json.JSONDecodeError, KeyError):
            raise HTTPException(
                status_code=500, detail="Invalid workflow status format in Redis."
            )

    try:
        workflow_uuid = UUID(workflow_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow ID format.")

    workflow_status = get_import_workflow_status(workflow_uuid)
    if workflow_status is None:
        raise HTTPException(status_code=404, detail="Workflow ID not found.")

    return {"workflow_id": workflow_id, "status": workflow_status.value}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_URL"),
        port=int(os.getenv("SERVER_PORT")),
        reload=False,
    )
