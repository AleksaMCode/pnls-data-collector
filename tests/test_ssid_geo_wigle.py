import unittest
from unittest.mock import patch

import httpx

from ssid_geo_mapper.exceptions.wigle import (
    WigleAbortRunError,
    WigleAccessDeniedError,
    WigleLookupError,
    WigleRateLimitError,
)
from ssid_geo_mapper.report import MappingRunStats, build_summary, format_duration
from ssid_geo_mapper.wigle_adapter.wigle import Wigle


def _response(status_code: int, **kwargs) -> httpx.Response:
    return httpx.Response(
        status_code, request=httpx.Request("GET", Wigle.URL), **kwargs
    )


class TestWigleLookup(unittest.TestCase):
    def setUp(self):
        self.wigle = Wigle(api_key="key", api_secret="secret")

    def _lookup(self, response, ssid="home"):
        with patch.object(httpx.Client, "get", return_value=response) as get:
            try:
                return self.wigle.lookup_SSID(ssid)
            finally:
                self.calls = get.call_count

    def test_429_raises_rate_limit_error_without_retrying(self):
        response = _response(
            429, headers={"Retry-After": "3600"}, text="too many queries today"
        )
        with self.assertRaises(WigleRateLimitError) as ctx:
            self._lookup(response)

        self.assertEqual(self.calls, 1)
        self.assertEqual(self.wigle.request_count, 1)
        self.assertEqual(ctx.exception.retry_after, "3600")
        self.assertEqual(ctx.exception.body, "too many queries today")

    def test_401_and_403_raise_access_denied_error_that_aborts_the_run(self):
        for status in (401, 403):
            with self.subTest(status=status):
                with self.assertRaises(WigleAccessDeniedError) as ctx:
                    self._lookup(_response(status, text="403 Forbidden"))
                self.assertIsInstance(ctx.exception, WigleAbortRunError)
                self.assertEqual(ctx.exception.status_code, status)
                self.assertEqual(ctx.exception.body, "403 Forbidden")
                self.assertIsNone(ctx.exception.retry_after)
                self.assertEqual(self.calls, 1)

    def test_other_bad_status_raises_lookup_error_with_body(self):
        for status in (400, 410, 500):
            with self.subTest(status=status):
                with self.assertRaises(WigleLookupError) as ctx:
                    self._lookup(_response(status, text="nope"))
                self.assertNotIsInstance(ctx.exception, WigleAbortRunError)
                self.assertEqual(ctx.exception.status_code, status)
                self.assertEqual(ctx.exception.body, "nope")
                self.assertEqual(self.calls, 1)

    def test_unusable_200_payloads_raise_lookup_error(self):
        payloads = [
            _response(200, text="<html>not json</html>"),
            _response(200, json={"success": False, "message": "too many queries"}),
            _response(200, json={"success": True}),
        ]
        for response in payloads:
            with self.subTest(body=response.text):
                with self.assertRaises(WigleLookupError):
                    self._lookup(response)

    def test_empty_results_return_empty_lists(self):
        locations, reduced = self._lookup(
            _response(200, json={"success": True, "results": []})
        )
        self.assertEqual(locations, [])
        self.assertEqual(reduced, [])

    def test_returns_only_exact_ssid_matches_without_duplicates(self):
        hit = {"ssid": "home", "trilat": 46.2, "trilong": 6.1, "country": "CH"}
        other = {"ssid": "Home", "trilat": 1.0, "trilong": 1.0, "country": "FR"}
        locations, _ = self._lookup(
            _response(200, json={"success": True, "results": [hit, dict(hit), other]})
        )
        self.assertEqual(
            locations, [{"ssid": "home", "lat": 46.2, "long": 6.1, "alpha2": "CH"}]
        )

    def test_timeout_propagates_and_counts_as_a_request(self):
        with patch.object(
            httpx.Client, "get", side_effect=httpx.ReadTimeout("slow")
        ) as get:
            with self.assertRaises(httpx.TimeoutException):
                self.wigle.lookup_SSID("home")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(self.wigle.request_count, 1)

    def test_non_ascii_ssid_is_sent_as_is(self):
        with patch.object(
            httpx.Client,
            "get",
            return_value=_response(200, json={"success": True, "results": []}),
        ) as get:
            self.wigle.lookup_SSID("Café ☕ 网络")
        self.assertEqual(get.call_args.kwargs["params"]["ssid"], "Café ☕ 网络")


class TestBuildSummary(unittest.TestCase):
    def test_completed_run(self):
        stats = MappingRunStats(
            request_budget=250,
            attempted=240,
            requests_sent=240,
            with_locations=31,
            no_results=205,
        )
        stats.failures.update({"400": 3, "timeout": 1})

        self.assertEqual(
            build_summary(stats, 612),
            "SSID GEO mapping completed in 10m 12s.\n"
            "Attempted: 240 | Requests sent: 240/250\n"
            "With locations: 31 | No results: 205 | Failed: 4\n"
            "Failures: 400 x3, timeout x1",
        )

    def test_rate_limited_run(self):
        stats = MappingRunStats(
            request_budget=250,
            attempted=187,
            requests_sent=187,
            with_locations=22,
            no_results=164,
            aborted_status=429,
            aborted_at_request=187,
            abort_body="too many queries today",
            abort_retry_after="3600",
        )

        summary = build_summary(stats, 440)

        self.assertTrue(
            summary.startswith(
                "SSID GEO mapping ABORTED after 7m 20s: 429 from WiGLE at request 187/250."
            )
        )
        self.assertIn("Retry-After: 3600", summary)
        self.assertIn("WiGLE said: too many queries today", summary)
        self.assertNotIn("Failures:", summary)

    def test_access_denied_run_flattens_html_body(self):
        stats = MappingRunStats(
            request_budget=250,
            attempted=1,
            requests_sent=1,
            aborted_status=403,
            aborted_at_request=1,
            abort_body="<html>\n<head><title>403 Forbidden</title></head>\n</html>",
        )

        summary = build_summary(stats, 2)

        self.assertTrue(
            summary.startswith(
                "SSID GEO mapping ABORTED after 2s: 403 from WiGLE at request 1/250."
            )
        )
        self.assertTrue(
            summary.endswith(
                "WiGLE said: <html> <head><title>403 Forbidden</title></head> </html>"
            )
        )

    def test_budget_exhausted_run(self):
        stats = MappingRunStats(
            request_budget=250, attempted=250, requests_sent=250, budget_exhausted=True
        )
        self.assertIn("request budget of 250 reached", build_summary(stats, 5))

    def test_format_duration(self):
        self.assertEqual(format_duration(9.7), "9s")
        self.assertEqual(format_duration(3725), "1h 2m 5s")
