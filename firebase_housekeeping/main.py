import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from firebase_housekeeping.core.firebase.helpers import (
    delete_all_by_nodes,
    download_all,
)
from firebase_housekeeping.core.mongo.helpers import insert_from_firebase_to_mongo
from firebase_housekeeping.settings import (
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
    SERVICE_VERSION,
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


@app.delete("/delete")
async def delete_all():
    logger.info("Delete workflow started.")
    data = download_all()
    insert_from_firebase_to_mongo(data)
    delete_all_by_nodes()
    logger.info("Delete workflow completed.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_URL"),
        port=int(os.getenv("SERVER_PORT")),
        reload=False,
    )
