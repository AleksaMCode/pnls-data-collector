import os
from http import HTTPStatus
from typing import Tuple

import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from ssid_geo_mapper.exceptions.wigle import (
    RetryableWigleError,
    wait_retry_after_or_exponential,
)
from ssid_geo_mapper.geo.reducer import reduce_locations
from util.logger import get_logger

logger = get_logger(__name__)

load_dotenv()


class Wigle:
    URL: str = "https://api.wigle.net/api/v2/network/search"

    def __init__(self, api_key=None, api_secret=None):
        if api_key and api_secret:
            self.api_key = api_key
            self.api_secret = api_secret
        else:
            self.api_key = os.getenv("WIGLE_API_KEY")
            self.api_secret = os.getenv("WIGLE_API_SECRET")
        self.auth = (self.api_key, self.api_secret)

    @retry(
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(RetryableWigleError),
        wait=wait_retry_after_or_exponential,
        reraise=True,
    )
    def lookup_SSID(
        self, ssid
    ) -> (
        Tuple[list[dict[str, str | float]], list[dict[str, str | float]]]
        | Tuple[None, None]
    ):
        # Normalize SSID
        # ssid = ssid.strip()
        params = {
            "first": 0,
            "freenet": "false",
            "paynet": "false",
            "ssid": ssid,
        }
        with httpx.Client(auth=self.auth, timeout=30.0) as client:
            r = client.get(self.URL, params=params)

        if r.status_code in (HTTPStatus.GONE, HTTPStatus.TOO_MANY_REQUESTS):
            retry_after = r.headers.get("Retry-After")
            raise RetryableWigleError(
                f"Retryable status {r.status_code} for SSID {ssid}",
                retry_after=retry_after,
            )
        if not (200 <= r.status_code < 300):
            # Stop the mapping workflow here if HTTPStatus.BAD_REQUEST, HTTPStatus.PAYMENT_REQUIRED or any other error.
            msg = f"Unable to lookup {ssid}, bad status: {r.status_code}"
            logger.error(msg)
            raise Exception(msg)

        try:
            result = r.json()
            locations = self._location_duplicate_reducer(
                self._location_formatter(result["results"], ssid)
            )
            reduced_locations = reduce_locations(locations)
            return locations, reduced_locations
        except Exception as e:
            logger.error(f"Unable to decode JSON response for SSID {ssid}: {e}")
            return None, None

    def _location_formatter(self, locations: list[dict[str, str | float]], ssid: str):
        return [
            {
                "ssid": l["ssid"],
                "lat": l["trilat"],
                "long": l["trilong"],
                "alpha2": l["country"],
            }
            for l in filter(lambda x: x["ssid"] == ssid, locations)
        ]

    def _location_duplicate_reducer(self, locations: list[dict[str, str | float]]):
        seen_coords = set()
        unique_locations = []

        for location in locations:
            lat = location["lat"]
            lon = location["long"]
            coord_key = (lat, lon)

            if coord_key in seen_coords:
                continue

            seen_coords.add(coord_key)
            unique_locations.append(
                {
                    "ssid": location["ssid"],
                    "lat": lat,
                    "long": lon,
                    "alpha2": location["alpha2"],
                }
            )

        return unique_locations
