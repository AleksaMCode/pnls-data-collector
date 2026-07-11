import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from stats.core.orm.helpers import get_daily_totals_all_devices, get_latest_import_date
from stats.core.supabase.helpers import (
    public_mac_all,
    public_probes_all,
    publish_device_daily_imports_today,
    publish_device_manufacturer_stats_all,
    publish_manufacturer_stats_all,
    publish_ssid_all,
    publish_ssid_stats_all_batched,
)
from stats.settings import SERVICE_DESCRIPTION, SERVICE_NAME, SERVICE_VERSION, TIMEZONE
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


@app.post("/stats", status_code=202)
async def publish_stats():
    latest_import_date = get_latest_import_date()
    daily_totals = get_daily_totals_all_devices(start_date=latest_import_date)

    if not daily_totals:
        msg = f"No daily totals available from {latest_import_date}."
        logger.info(msg)
        return {"status": "skipped", "message": msg}

    publish_ssid_all(daily_totals=daily_totals)
    public_mac_all(daily_totals=daily_totals)
    public_probes_all(daily_totals=daily_totals)
    publish_device_daily_imports_today(tz=TIMEZONE, import_date=latest_import_date)
    publish_device_manufacturer_stats_all(target_date=latest_import_date)
    publish_manufacturer_stats_all()
    publish_ssid_stats_all_batched(updated_from=latest_import_date)

    msg = (
        f"Published daily totals to Supabase for {len(daily_totals)} day(s), "
        f"starting from {latest_import_date}."
    )
    logger.info(msg)
    return {"status": "completed", "message": msg, "start_date": latest_import_date}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_URL", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "9097")),
        reload=False,
    )
