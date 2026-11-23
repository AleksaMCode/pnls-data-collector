import os
import random
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from tqdm import tqdm

from ssid_geo_mapper.core.orm.helpers import (
    get_unmapped_ssids,
    insert_ssid_geo_batch,
    update_ssid_mapped,
)
from ssid_geo_mapper.exceptions.wigle import WigleAbortRunError, WigleLookupError
from ssid_geo_mapper.report import MappingRunStats, build_summary
from ssid_geo_mapper.settings import (
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
    SERVICE_VERSION,
    SLACK_WEBHOOK_URL,
    WIGLE_API_LIMIT,
    WIGLE_BASE_DELAY_SECONDS,
    WIGLE_BATCH_SIZE,
    WIGLE_DELAY_JITTER_SECONDS,
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
    stats = MappingRunStats(request_budget=WIGLE_API_LIMIT)
    started = time.monotonic()
    ssids = get_unmapped_ssids(WIGLE_BATCH_SIZE)

    for index, ssid in enumerate(tqdm(ssids, desc="Mapping SSIDs")):
        # Every HTTP call counts against the budget, not every SSID.
        if wigle.request_count >= WIGLE_API_LIMIT:
            stats.budget_exhausted = True
            logger.error(
                f"Request budget of {WIGLE_API_LIMIT} reached. Stopping the run."
            )
            break

        if index > 0:
            # Proactively pace outgoing Wigle lookups to avoid hitting rate limits.
            time.sleep(
                WIGLE_BASE_DELAY_SECONDS
                + random.uniform(0.0, WIGLE_DELAY_JITTER_SECONDS)
            )

        stats.attempted += 1
        try:
            logger.info(
                f"Mapping SSID '{ssid.ssid}' using WIGLE API. "
                f"Request: {wigle.request_count + 1}/{WIGLE_API_LIMIT}"
            )
            locations, reduced_locations = wigle.lookup_SSID(ssid.ssid)

            if not locations:
                # If there is no location, the SSID is mapped with GEO location flag set to False.
                update_ssid_mapped(ssid.id, has_geo=False)
                stats.no_results += 1
                continue

            insert_ssid_geo_batch(ssid.id, locations, reduced_locations)
            stats.with_locations += 1
            logger.info(
                f"Mapping SSID '{ssid.ssid}' complete with {len(locations)} locations."
            )
        except WigleAbortRunError as e:
            # Quota spent (429) or access denied (401/403): any further request is wasted.
            # The SSID stays unmapped and is picked up by the next run.
            stats.aborted_status = e.status_code
            stats.aborted_at_request = wigle.request_count
            stats.abort_body = e.body
            stats.abort_retry_after = e.retry_after
            logger.error(
                f"WiGLE returned {e.status_code} at request "
                f"{wigle.request_count}/{WIGLE_API_LIMIT}. Aborting the run."
            )
            break
        except WigleLookupError as e:
            reason = (
                str(e.status_code)
                if e.status_code and not 200 <= e.status_code < 300
                else "bad payload"
            )
            stats.failures[reason] += 1
            logger.error(f"Mapping SSID '{ssid.ssid}' failed. Exception: {str(e)}")
        except httpx.TimeoutException as e:
            stats.failures["timeout"] += 1
            logger.error(f"Mapping SSID '{ssid.ssid}' timed out. Exception: {repr(e)}")
        except Exception as e:
            stats.failures[type(e).__name__] += 1
            logger.error(f"Mapping SSID '{ssid.ssid}' failed. Exception: {repr(e)}")

    stats.requests_sent = wigle.request_count
    msg = build_summary(stats, time.monotonic() - started)
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
