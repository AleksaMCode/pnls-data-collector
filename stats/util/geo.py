from collections.abc import Iterable

# Published coordinates are rounded to 2 decimals (about 1 km). The reduced points are exact WiGLE coordinates,
# so for an SSID with a single location they would otherwise publish a precise position (e.g. a home address)
# next to the network name. The local tables keep the exact values.
GEO_COORDINATE_DECIMALS = 2


def build_ssid_geo_payloads(rows: Iterable) -> list[dict]:
    """
    Groups reduced geolocation points into one publishable entry per SSID.

    :param rows: Points with `ssid`, `latitude`, `longitude`, `country_alpha3` and `created_date` attributes.
    :return: One dictionary per SSID with keys `ssid`, `geo` (list of `{"lat", "lon", "cc"}`)
        and `geo_updated` (ISO date of the newest point). SSIDs without a usable point are left out.
    """
    grouped: dict[str, dict] = {}

    for row in rows:
        if row.latitude is None or row.longitude is None:
            continue

        lat = round(float(row.latitude), GEO_COORDINATE_DECIMALS)
        lon = round(float(row.longitude), GEO_COORDINATE_DECIMALS)

        entry = grouped.setdefault(
            row.ssid, {"points": {}, "geo_updated": row.created_date}
        )
        # Rounding can collapse two points into one. Keep the first.
        entry["points"].setdefault(
            (lat, lon), {"lat": lat, "lon": lon, "cc": row.country_alpha3}
        )
        if row.created_date > entry["geo_updated"]:
            entry["geo_updated"] = row.created_date

    return [
        {
            "ssid": ssid,
            "geo": list(entry["points"].values()),
            "geo_updated": entry["geo_updated"].isoformat(),
        }
        for ssid, entry in grouped.items()
    ]
