import os
from typing import Literal

from core.supabase.helpers import (
    fetch_all_data_series,
    fetch_device_data_series,
    fetch_last_n_days_totals,
    fetch_last_n_days_totals_with_series,
    fetch_manufacturers_data,
    fetch_monthly_totals_all_devices,
    fetch_previous_n_days_totals,
    fetch_probe_requests_per_device_last_n_days,
    fetch_sankey_data,
    fetch_ssid_stats,
    fetch_total_per_device_stats,
    fetch_total_stats,
)
from dotenv import load_dotenv
from fastapi import APIRouter, Query
from fastapi_cache.decorator import cache
from routers.models import DeviceEnum
from settings import TIMEZONE

router = APIRouter(prefix="/stats", tags=["stats"])
load_dotenv()
CACHE_TTL = int(os.getenv("REDIS_TTL", "3600"))


@router.get("/total")
@cache(expire=CACHE_TTL)
async def get_total_stats():
    return fetch_total_stats()


@router.get("/last-30-days")
@cache(expire=CACHE_TTL)
async def get_last_30_days_totals():
    return fetch_last_n_days_totals(n_days=30, tz=TIMEZONE)


@router.get("/last-30-days/totals-with-series")
@cache(expire=CACHE_TTL)
async def get_last_30_days_totals_with_series():
    return fetch_last_n_days_totals_with_series(n_days=30, tz=TIMEZONE)


@router.get("/previous-30-days/totals")
@cache(expire=CACHE_TTL)
async def get_previous_30_days_totals():
    return fetch_previous_n_days_totals(n_days=30, tz=TIMEZONE)


@router.get("/probe-requests-per-device")
@cache(expire=CACHE_TTL)
async def get_probe_requests_per_device_last_n_days(
    n_days: int = Query(default=30, ge=1, le=365)
):
    return fetch_probe_requests_per_device_last_n_days(n_days=n_days, tz=TIMEZONE)


@router.get("/monthly-totals")
@cache(expire=CACHE_TTL)
async def get_monthly_totals_all_devices():
    return fetch_monthly_totals_all_devices()


@router.get("/series")
@cache(expire=CACHE_TTL)
async def get_all_data_series():
    return fetch_all_data_series(tz=TIMEZONE)


@router.get("/series/{device_name}")
@cache(expire=CACHE_TTL)
async def get_device_data_series(device_name: DeviceEnum):
    return fetch_device_data_series(device_name=device_name.value, tz=TIMEZONE)


@router.get("/devices")
@cache(expire=CACHE_TTL)
async def get_total_per_device_stats():
    return fetch_total_per_device_stats()


@router.get("/manufacturers")
@cache(expire=CACHE_TTL)
async def get_manufacturers_data():
    return fetch_manufacturers_data()


@router.get("/sankey")
@cache(expire=CACHE_TTL)
async def get_sankey_data():
    return fetch_sankey_data()


@router.get("/ssids")
async def get_ssid_stats(
    search: str | None = Query(default=None),
    sort_by: Literal["ssid", "seen_count", "first_seen", "last_seen"] = Query(
        default="last_seen"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
):
    return fetch_ssid_stats(
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
    )
