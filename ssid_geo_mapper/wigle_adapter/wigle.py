import os
from http import HTTPStatus
from typing import Tuple

import httpx
from dotenv import load_dotenv

from ssid_geo_mapper.exceptions.wigle import (
    WigleAccessDeniedError,
    WigleLookupError,
    WigleRateLimitError,
)
from ssid_geo_mapper.geo.reducer import reduce_locations
from util.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

# Max. number of response body characters kept for logs and notifications.
BODY_SNIPPET_LENGTH = 500


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
        # Every HTTP call sent to WiGLE, whatever its outcome. Used to enforce the request budget.
        self.request_count = 0

    def lookup_SSID(
        self, ssid
    ) -> Tuple[list[dict[str, str | float]], list[dict[str, str | float]]]:
        """Looks up a single SSID with exactly one WiGLE request (no retries).

        Raises:
            WigleRateLimitError: on 429. The caller must stop the whole run.
            WigleAccessDeniedError: on 401 or 403. The caller must stop the whole run.
            WigleLookupError: on any other non-2xx status or an unusable payload.
            httpx.HTTPError: on transport problems such as timeouts.
        """
        params = {
            "first": 0,
            "freenet": "false",
            "paynet": "false",
            "ssid": ssid,
        }
        self.request_count += 1
        with httpx.Client(auth=self.auth, timeout=30.0) as client:
            r = client.get(self.URL, params=params)

        body = r.text[:BODY_SNIPPET_LENGTH]

        if r.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            retry_after = r.headers.get("Retry-After")
            msg = (
                f"Rate limited (429) on SSID {ssid!r}. "
                f"Retry-After: {retry_after}. Body: {body}"
            )
            logger.error(msg)
            raise WigleRateLimitError(
                msg, status_code=r.status_code, body=body, retry_after=retry_after
            )

        if r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            msg = f"Access denied ({r.status_code}) on SSID {ssid!r}. Body: {body}"
            logger.error(msg)
            raise WigleAccessDeniedError(msg, status_code=r.status_code, body=body)

        if not (200 <= r.status_code < 300):
            msg = (
                f"Unable to lookup {ssid!r}, bad status: {r.status_code}. Body: {body}"
            )
            logger.error(msg)
            raise WigleLookupError(msg, status_code=r.status_code, body=body)

        try:
            result = r.json()
        except ValueError as e:
            msg = f"Unable to decode JSON response for SSID {ssid!r}: {e}. Body: {body}"
            logger.error(msg)
            raise WigleLookupError(msg, status_code=r.status_code, body=body) from e

        if (
            not isinstance(result, dict)
            or result.get("success") is False
            or not isinstance(result.get("results"), list)
        ):
            msg = f"Unusable WiGLE payload for SSID {ssid!r}. Body: {body}"
            logger.error(msg)
            raise WigleLookupError(msg, status_code=r.status_code, body=body)

        locations = self._location_duplicate_reducer(
            self._location_formatter(result["results"], ssid)
        )
        reduced_locations = reduce_locations(locations)
        return locations, reduced_locations

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
