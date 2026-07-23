from datetime import date

from sqlalchemy import asc, desc, func

from util.util import (
    last_n_dates_excluding_today,
    previous_n_dates_before_last_n,
    scalar_to_int,
    today_in_tz,
)

from . import _session
from .models import (
    DailyImportsMac,
    DailyImportsProbes,
    DailyImportsSsid,
    Device,
    DeviceDailyImports,
    DeviceManufacturerStats,
    ManufacturerStats,
    SsidStats,
    UniqueTotalStats,
)


def _date_sum_map(model, dates: list[date]) -> dict[date, int]:
    if not dates:
        return {}

    with _session() as db:
        rows = (
            db.query(model.date, func.sum(model.count))
            .filter(model.date.in_(dates))
            .group_by(model.date)
            .all()
        )
    return {row[0]: int(row[1] or 0) for row in rows}


def _avg_count_before_date(model, end_date: date) -> int:
    with _session() as db:
        avg_value = (
            db.query(func.avg(model.count)).filter(model.date < end_date).scalar()
        )
    return int(round(float(avg_value or 0)))


def fetch_last_n_days_totals(n_days: int = 30, tz: str = "Europe/Paris") -> dict:
    dates = last_n_dates_excluding_today(n_days=n_days, tz=tz)
    mac_map = _date_sum_map(DailyImportsMac, dates)
    probes_map = _date_sum_map(DailyImportsProbes, dates)
    ssid_map = _date_sum_map(DailyImportsSsid, dates)

    return {
        "macCount": sum(mac_map.get(d, 0) for d in dates),
        "probeRequestCount": sum(probes_map.get(d, 0) for d in dates),
        "ssidCount": sum(ssid_map.get(d, 0) for d in dates),
    }


def fetch_average_daily_counts(tz: str = "Europe/Paris") -> dict:
    today = today_in_tz(tz)
    return {
        "macCount": _avg_count_before_date(DailyImportsMac, today),
        "probeRequestCount": _avg_count_before_date(DailyImportsProbes, today),
        "ssidCount": _avg_count_before_date(DailyImportsSsid, today),
    }


def fetch_last_n_days_totals_with_series(
    n_days: int = 30, tz: str = "Europe/Paris"
) -> dict:
    dates = last_n_dates_excluding_today(n_days=n_days, tz=tz)
    mac_map = _date_sum_map(DailyImportsMac, dates)
    probes_map = _date_sum_map(DailyImportsProbes, dates)
    ssid_map = _date_sum_map(DailyImportsSsid, dates)

    mac_series = [mac_map.get(d, 0) for d in dates]
    probe_series = [probes_map.get(d, 0) for d in dates]
    ssid_series = [ssid_map.get(d, 0) for d in dates]

    return {
        "totals": {
            "macCount": sum(mac_series),
            "probeRequestCount": sum(probe_series),
            "ssidCount": sum(ssid_series),
        },
        "series": {
            "macCount": mac_series,
            "probeRequestCount": probe_series,
            "ssidCount": ssid_series,
        },
    }


def fetch_previous_n_days_totals(n_days: int = 30, tz: str = "Europe/Paris") -> dict:
    dates = previous_n_dates_before_last_n(n_days=n_days, tz=tz)
    mac_map = _date_sum_map(DailyImportsMac, dates)
    probes_map = _date_sum_map(DailyImportsProbes, dates)
    ssid_map = _date_sum_map(DailyImportsSsid, dates)

    return {
        "totals": {
            "macCount": sum(mac_map.get(d, 0) for d in dates),
            "probeRequestCount": sum(probes_map.get(d, 0) for d in dates),
            "ssidCount": sum(ssid_map.get(d, 0) for d in dates),
        }
    }


def fetch_probe_requests_per_device_last_n_days(
    n_days: int = 30, tz: str = "Europe/Paris"
) -> dict[str, list[int]]:
    today = today_in_tz(tz)

    with _session() as db:
        date_rows = (
            db.query(DeviceDailyImports.date)
            .filter(DeviceDailyImports.date < today)
            .distinct()
            .order_by(DeviceDailyImports.date)
            .all()
        )
        filtered_dates = [row[0] for row in date_rows][-n_days:]

        if not filtered_dates:
            return {}

        rows = (
            db.query(
                DeviceDailyImports.date,
                DeviceDailyImports.device_id,
                DeviceDailyImports.probes,
            )
            .filter(DeviceDailyImports.date.in_(filtered_dates))
            .order_by(DeviceDailyImports.date, DeviceDailyImports.device_id)
            .all()
        )

    per_device: dict[str, list[int]] = {}
    for _, device_id, probes in rows:
        per_device.setdefault(device_id, []).append(scalar_to_int(probes))
    return per_device


def fetch_monthly_totals_all_devices() -> dict:
    with _session() as db:
        rows = (
            db.query(
                func.to_char(DeviceDailyImports.date, "YYYY-MM").label("month_key"),
                func.sum(DeviceDailyImports.probes).label("probe_requests"),
                func.sum(DeviceDailyImports.ssid).label("ssid"),
                func.sum(DeviceDailyImports.mac).label("mac"),
            )
            .group_by("month_key")
            .order_by("month_key")
            .all()
        )

    return {
        row.month_key: {
            "probe_requests": scalar_to_int(row.probe_requests),
            "ssid": scalar_to_int(row.ssid),
            "mac": scalar_to_int(row.mac),
        }
        for row in rows
    }


def fetch_all_data_series(tz: str = "Europe/Paris") -> dict:
    today = today_in_tz(tz)

    with _session() as db:
        date_rows = (
            db.query(DeviceDailyImports.date)
            .filter(DeviceDailyImports.date < today)
            .distinct()
            .order_by(DeviceDailyImports.date)
            .all()
        )
        dates = [row[0] for row in date_rows]

    if not dates:
        return {
            "macCount": [],
            "probeRequestCount": [],
            "ssidCount": [],
            "dayCounts": 0,
        }

    mac_map = _date_sum_map(DailyImportsMac, dates)
    probes_map = _date_sum_map(DailyImportsProbes, dates)
    ssid_map = _date_sum_map(DailyImportsSsid, dates)

    return {
        "macCount": [mac_map.get(d, 0) for d in dates],
        "probeRequestCount": [probes_map.get(d, 0) for d in dates],
        "ssidCount": [ssid_map.get(d, 0) for d in dates],
        "dayCounts": len(dates),
    }


def fetch_device_data_series(device_name: str, tz: str = "Europe/Paris") -> dict:
    today = today_in_tz(tz)

    with _session() as db:
        date_rows = (
            db.query(DeviceDailyImports.date)
            .filter(DeviceDailyImports.date < today)
            .distinct()
            .order_by(DeviceDailyImports.date)
            .all()
        )
        dates = [row[0] for row in date_rows]

        device_rows = (
            db.query(
                DeviceDailyImports.date,
                DeviceDailyImports.mac,
                DeviceDailyImports.probes,
                DeviceDailyImports.ssid,
            )
            .filter(
                DeviceDailyImports.device_id == device_name,
                DeviceDailyImports.date.in_(dates),
            )
            .all()
        )

    row_by_date = {row.date: row for row in device_rows}

    mac_series = []
    probe_series = []
    ssid_series = []
    for d in dates:
        row = row_by_date.get(d)
        if row is None:
            mac_series.append(0)
            probe_series.append(0)
            ssid_series.append(0)
        else:
            mac_series.append(scalar_to_int(row.mac))
            probe_series.append(scalar_to_int(row.probes))
            ssid_series.append(scalar_to_int(row.ssid))

    return {
        "macCount": mac_series,
        "probeRequestCount": probe_series,
        "ssidCount": ssid_series,
        "dayCounts": len(dates),
    }


def fetch_total_per_device_stats() -> dict:
    with _session() as db:
        device_rows = db.query(Device).all()
        aggregates = (
            db.query(
                DeviceDailyImports.device_id,
                func.sum(DeviceDailyImports.mac).label("mac"),
                func.sum(DeviceDailyImports.probes).label("probe_requests"),
                func.sum(DeviceDailyImports.ssid).label("ssid"),
            )
            .group_by(DeviceDailyImports.device_id)
            .all()
        )

    totals_per_device: dict[str, dict] = {}
    aggregate_by_device = {row.device_id: row for row in aggregates}

    for device in device_rows:
        agg = aggregate_by_device.get(device.device)
        totals_per_device[device.device] = {
            "mac": scalar_to_int(agg.mac if agg else 0),
            "probe_requests": scalar_to_int(agg.probe_requests if agg else 0),
            "ssid": scalar_to_int(agg.ssid if agg else 0),
            "location": device.location,
            "coordinates": device.coordinates,
        }

    # Include any device data that exists only in imports.
    for device_id, agg in aggregate_by_device.items():
        if device_id in totals_per_device:
            continue
        totals_per_device[device_id] = {
            "mac": scalar_to_int(agg.mac),
            "probe_requests": scalar_to_int(agg.probe_requests),
            "ssid": scalar_to_int(agg.ssid),
            "location": None,
            "coordinates": None,
        }

    return totals_per_device


def fetch_total_stats() -> dict:
    with _session() as db:
        probes_total = db.query(func.sum(DailyImportsProbes.count)).scalar()
        unique_ssid_total = db.query(func.count(SsidStats.id)).scalar()
        latest_unique_totals = (
            db.query(UniqueTotalStats)
            .order_by(UniqueTotalStats.date.desc(), UniqueTotalStats.id.desc())
            .first()
        )

    snapshot_mac_total = None
    if latest_unique_totals and isinstance(latest_unique_totals.totals, dict):
        snapshot_mac_total = latest_unique_totals.totals.get("macCount")

    return {
        "macCount": scalar_to_int(
            snapshot_mac_total
            if snapshot_mac_total is not None
            else db.query(func.sum(DailyImportsMac.count)).scalar()
        ),
        "ssidCount": scalar_to_int(
            unique_ssid_total
            if unique_ssid_total not in (None, 0)
            else db.query(func.sum(DailyImportsSsid.count)).scalar()
        ),
        "probeRequestCount": scalar_to_int(probes_total),
    }


def fetch_manufacturers_data() -> list[dict]:
    with _session() as db:
        rows = (
            db.query(ManufacturerStats)
            .order_by(ManufacturerStats.total_occurrences.desc())
            .all()
        )

    return [
        {
            "company": row.company,
            "country": row.country_alpha3,
            "count": scalar_to_int(row.total_occurrences),
            "percentage": float(row.percentage or 0),
        }
        for row in rows
    ]


def fetch_sankey_data() -> dict:
    with _session() as db:
        rows = (
            db.query(DeviceManufacturerStats)
            .order_by(
                DeviceManufacturerStats.date.desc(), DeviceManufacturerStats.id.desc()
            )
            .all()
        )

    # Keep only latest snapshot per device.
    latest_by_device: dict[str, DeviceManufacturerStats] = {}
    for row in rows:
        if row.device_id not in latest_by_device:
            latest_by_device[row.device_id] = row

    sankey_data: dict[str, dict] = {}
    for device_id, row in latest_by_device.items():
        sankey_data[device_id] = {}
        manufacturer_data = row.manufacturer_data or []
        if not isinstance(manufacturer_data, list):
            continue
        for item in manufacturer_data:
            if not isinstance(item, dict):
                continue
            company = item.get("company")
            if not company:
                continue
            sankey_data[device_id][company] = {
                "country": item.get("country"),
            }

    return sankey_data


def fetch_ssid_stats(
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "last_seen",
    sort_order: str = "desc",
    search: str | None = None,
) -> dict:
    sort_columns = {
        "ssid": SsidStats.ssid,
        "seen_count": SsidStats.seen_count,
        "first_seen": SsidStats.first_seen,
        "last_seen": SsidStats.last_seen,
    }
    sort_column = sort_columns.get(sort_by, SsidStats.last_seen)
    sort_direction = asc if sort_order == "asc" else desc

    with _session() as db:
        query = db.query(SsidStats)

        if search:
            query = query.filter(SsidStats.ssid.ilike(f"%{search}%"))

        total = query.count()
        rows = (
            query.order_by(sort_direction(sort_column))
            .offset(offset)
            .limit(limit)
            .all()
        )

    return {
        "items": [
            {
                "ssid": row.ssid,
                "seen_count": scalar_to_int(row.seen_count),
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
            }
            for row in rows
        ],
        "pagination": {
            "offset": offset,
            "limit": limit,
            "total": total,
        },
        "sorting": {
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    }


def fetch_ssid_export_rows(
    sort_by: str = "last_seen",
    sort_order: str = "desc",
    search: str | None = None,
) -> list[dict]:
    sort_columns = {
        "ssid": SsidStats.ssid,
        "seen_count": SsidStats.seen_count,
        "first_seen": SsidStats.first_seen,
        "last_seen": SsidStats.last_seen,
    }
    sort_column = sort_columns.get(sort_by, SsidStats.last_seen)
    sort_direction = asc if sort_order == "asc" else desc

    with _session() as db:
        query = db.query(SsidStats)
        if search:
            query = query.filter(SsidStats.ssid.ilike(f"%{search}%"))
        rows = query.order_by(sort_direction(sort_column)).all()

    return [
        {
            "ssid": row.ssid,
            "seen_count": scalar_to_int(row.seen_count),
            "first_seen": row.first_seen,
            "last_seen": row.last_seen,
        }
        for row in rows
    ]
