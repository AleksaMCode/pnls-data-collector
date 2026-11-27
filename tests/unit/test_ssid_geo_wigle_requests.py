"""Unit tests for the requests the WiGLE adapter sends and the results it keeps, on a fake transport."""

import base64
import json
import unittest
from unittest import mock

import httpx

from tests.support.ssid_geo_loader import import_ssid_geo_module

wigle_module = import_ssid_geo_module("ssid_geo_mapper.wigle_adapter.wigle")
wigle_errors = import_ssid_geo_module("ssid_geo_mapper.exceptions.wigle")


def result(ssid="home", lat=46.2, long=6.14, country="CH", **extra):
    return {"ssid": ssid, "trilat": lat, "trilong": long, "country": country, **extra}


class WigleRequestTestCase(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.clients = []
        self.payload = {"success": True, "results": [result()]}
        real_client = httpx.Client

        def client(**kwargs):
            self.clients.append(kwargs)
            return real_client(transport=httpx.MockTransport(self.answer), **kwargs)

        patcher = mock.patch.object(wigle_module.httpx, "Client", side_effect=client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.payload)

    def lookup(self, ssid="home", wigle=None):
        wigle = wigle or wigle_module.Wigle(api_key="key", api_secret="secret")
        return wigle.lookup_SSID(ssid)


class TestWigleRequest(WigleRequestTestCase):
    def test_search_parameters(self):
        self.lookup("CERN Guest")

        (request,) = self.requests
        self.assertEqual(str(request.url.copy_with(query=None)), wigle_module.Wigle.URL)
        self.assertEqual(
            dict(request.url.params),
            {"first": "0", "freenet": "false", "paynet": "false", "ssid": "CERN Guest"},
        )

    def test_basic_auth_with_the_given_credentials(self):
        self.lookup()

        expected = base64.b64encode(b"key:secret").decode()
        self.assertEqual(self.requests[0].headers["Authorization"], f"Basic {expected}")

    def test_credentials_come_from_the_environment_by_default(self):
        with mock.patch.dict(
            "os.environ", {"WIGLE_API_KEY": "env-key", "WIGLE_API_SECRET": "env-secret"}
        ):
            wigle = wigle_module.Wigle()

        self.lookup(wigle=wigle)

        expected = base64.b64encode(b"env-key:env-secret").decode()
        self.assertEqual(self.requests[0].headers["Authorization"], f"Basic {expected}")

    def test_request_times_out_after_30_seconds(self):
        self.lookup()

        self.assertEqual(self.clients[0]["timeout"], 30.0)

    def test_each_lookup_is_one_request(self):
        wigle = wigle_module.Wigle(api_key="key", api_secret="secret")

        self.lookup("a", wigle)
        self.lookup("b", wigle)

        self.assertEqual(wigle.request_count, 2)
        self.assertEqual(len(self.requests), 2)


class TestWigleResults(WigleRequestTestCase):
    def test_locations_and_their_reduced_set(self):
        self.payload["results"] = [
            result(lat=46.20, long=6.14),  # Geneva
            result(lat=46.23, long=6.07),  # Meyrin, ~6 km away: reduced away.
            result(lat=48.85, long=2.35, country="FR"),  # Paris
        ]

        locations, reduced = self.lookup()

        self.assertEqual(
            [(loc["lat"], loc["long"], loc["alpha2"]) for loc in locations],
            [(46.20, 6.14, "CH"), (46.23, 6.07, "CH"), (48.85, 2.35, "FR")],
        )
        self.assertEqual(
            [(loc["lat"], loc["long"]) for loc in reduced],
            [(46.20, 6.14), (48.85, 2.35)],
        )

    def test_ssid_match_is_case_sensitive(self):
        self.payload["results"] = [result(ssid="home"), result(ssid="Home", lat=1.0)]

        locations, _ = self.lookup("home")

        self.assertEqual([loc["ssid"] for loc in locations], ["home"])

    def test_location_without_a_country_is_kept(self):
        self.payload["results"] = [result(country=None)]

        locations, reduced = self.lookup()

        self.assertIsNone(locations[0]["alpha2"])
        self.assertIsNone(reduced[0]["alpha2"])

    def test_extra_fields_are_not_kept(self):
        self.payload["results"] = [result(netid="AA:BB:CC:DD:EE:FF", channel=6)]

        locations, _ = self.lookup()

        self.assertEqual(sorted(locations[0]), ["alpha2", "lat", "long", "ssid"])

    def test_json_body_that_is_not_an_object_is_a_lookup_error(self):
        self.payload = json.loads("[]")

        with self.assertRaises(wigle_errors.WigleLookupError):
            self.lookup()

    @unittest.expectedFailure
    def test_result_without_coordinates_is_a_lookup_error(self):
        """Known bug: a result missing `trilong` raises KeyError, which the run records as
        "KeyError" instead of "bad payload". Remove the decorator once results are validated.
        """
        self.payload["results"] = [{"ssid": "home", "trilat": 46.2, "country": "CH"}]

        with self.assertRaises(wigle_errors.WigleLookupError):
            self.lookup()


if __name__ == "__main__":
    unittest.main()
