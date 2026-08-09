import math

# Radius of the Earth in kilometers
R = 6371


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance = R * c
    return distance


def reduce_locations(
    locations: list[dict[str, str | float]], threshold_km: float = 27.0
) -> list[dict[str, str]]:
    """
    Filters out coordinates from the data that are too close to each other (based on the threshold distance).

    :param locations: List of dictionaries with keys 'ssid', 'lat', 'long', 'alpha2'
    :param threshold_km: Distance in kilometers; points closer than this will be considered duplicates
    :return: List of distinct locations (only ssid, lat, long, and alpha2)
    """
    distinct_locations = []

    for location in locations:
        lat, lon = location["lat"], location["long"]
        distinct = True
        for unique_entry in distinct_locations:
            u_lat, u_lon = unique_entry["lat"], unique_entry["long"]
            # Check if the distance between the current point and any unique point is below the threshold
            if haversine(lat, lon, u_lat, u_lon) < threshold_km:
                distinct = False
                break
        if distinct:
            distinct_locations.append(
                {
                    "ssid": location["ssid"],
                    "lat": lat,
                    "long": lon,
                    "alpha2": location["alpha2"],
                }
            )

    return distinct_locations
