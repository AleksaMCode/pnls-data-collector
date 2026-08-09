import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from tqdm import tqdm

from ssid_geo_mapper.core.orm.helpers import (
    get_unmapped_ssids,
    insert_ssid_geo_batch,
    update_ssid_mapped,
)
from ssid_geo_mapper.settings import (
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
    SERVICE_VERSION,
    SLACK_WEBHOOK_URL,
    WIGLE_API_LIMIT,
)
from ssid_geo_mapper.wigle_adapter.wigle import Wigle
from util.logger import get_logger
from util.mattermost.helpers import MattermostBot, send_webhook_message

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


@app.post(
    "/ssid_mapping",
    summary="Maps SSIDs from DB",
)
async def ssid_mapping():
    msg = "SSID GEO mapping workflow started."
    logger.info(msg)
    send_webhook_message(
        msg,
        webhook=SLACK_WEBHOOK_URL,
        bot_name=MattermostBot.SSID_GEO_MAPPER,
    )
    wigle = Wigle()
    count = 0
    ssids = get_unmapped_ssids(WIGLE_API_LIMIT)

    for ssid in tqdm(ssids, desc="Mapping SSIDs"):
        count += 1
        try:
            logger.info(
                f"Mapping SSID '{ssid.ssid}' using WIGLE API. Count: {count}/{WIGLE_API_LIMIT}"
            )
            locations, reduced_locations = wigle.lookup_SSID(ssid.ssid)

            if not locations:
                # If there is no location, the SSID is mapped with not GEO location
                update_ssid_mapped(ssid.id)
                continue

            insert_ssid_geo_batch(ssid.id, locations, reduced_locations)
            logger.info(f"Mapping SSID '{ssid}' complete.")
        except Exception as e:
            logger.error(f"Mapping SSID '{ssid}' failed. Exception: {str(e)}")
            logger.info(f"Total mapped: {count}/{WIGLE_API_LIMIT}")

    msg = (
        f"SSID GEO mapping workflow completed. Total mapped: {count}/{WIGLE_API_LIMIT}"
    )
    logger.info(msg)
    send_webhook_message(
        msg,
        webhook=SLACK_WEBHOOK_URL,
        bot_name=MattermostBot.SSID_GEO_MAPPER,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_URL"),
        port=int(os.getenv("SERVER_PORT")),
        reload=False,
    )
