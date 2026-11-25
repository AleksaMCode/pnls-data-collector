import unittest
from datetime import date
from types import SimpleNamespace

from stats.util.geo import GEO_COORDINATE_DECIMALS, build_ssid_geo_payloads


def _point(
    ssid: str,
    latitude: float | None,
    longitude: float | None,
    country_alpha3: str | None = "FRA",
    created_date: date = date(2026, 11, 20),
):
    return SimpleNamespace(
        ssid=ssid,
        latitude=latitude,
        longitude=longitude,
        country_alpha3=country_alpha3,
        created_date=created_date,
    )


class TestBuildSsidGeoPayloads(unittest.TestCase):
    def test_returns_empty_list_without_rows(self):
        self.assertEqual(build_ssid_geo_payloads([]), [])

    def test_groups_points_per_ssid(self):
        payloads = build_ssid_geo_payloads(
            [
                _point("CafeWifi", 48.85, 2.35),
                _point("HotelGuest", 45.76, 4.83),
                _point("CafeWifi", 43.6, 1.44),
            ]
        )

        self.assertEqual(
            payloads,
            [
                {
                    "ssid": "CafeWifi",
                    "geo": [
                        {"lat": 48.85, "lon": 2.35, "cc": "FRA"},
                        {"lat": 43.6, "lon": 1.44, "cc": "FRA"},
                    ],
                    "geo_updated": "2026-11-20",
                },
                {
                    "ssid": "HotelGuest",
                    "geo": [{"lat": 45.76, "lon": 4.83, "cc": "FRA"}],
                    "geo_updated": "2026-11-20",
                },
            ],
        )

    def test_rounds_coordinates_to_two_decimals(self):
        self.assertEqual(GEO_COORDINATE_DECIMALS, 2)

        payloads = build_ssid_geo_payloads(
            [_point("CafeWifi", 48.858370, -2.294481, "FRA")]
        )

        self.assertEqual(
            payloads[0]["geo"], [{"lat": 48.86, "lon": -2.29, "cc": "FRA"}]
        )

    def test_points_equal_after_rounding_are_published_once(self):
        payloads = build_ssid_geo_payloads(
            [
                _point("CafeWifi", 48.8512, 2.3491),
                _point("CafeWifi", 48.8544, 2.3519),
            ]
        )

        self.assertEqual(payloads[0]["geo"], [{"lat": 48.85, "lon": 2.35, "cc": "FRA"}])

    def test_skips_points_without_coordinates(self):
        payloads = build_ssid_geo_payloads(
            [
                _point("CafeWifi", None, 2.35),
                _point("CafeWifi", 48.85, None),
                _point("CafeWifi", 43.6, 1.44),
            ]
        )

        self.assertEqual(payloads[0]["geo"], [{"lat": 43.6, "lon": 1.44, "cc": "FRA"}])

    def test_leaves_out_ssids_without_any_usable_point(self):
        payloads = build_ssid_geo_payloads(
            [_point("NoCoords", None, None), _point("CafeWifi", 48.85, 2.35)]
        )

        self.assertEqual([payload["ssid"] for payload in payloads], ["CafeWifi"])

    def test_geo_updated_is_the_newest_created_date(self):
        payloads = build_ssid_geo_payloads(
            [
                _point("CafeWifi", 48.85, 2.35, created_date=date(2026, 11, 18)),
                _point("CafeWifi", 43.6, 1.44, created_date=date(2026, 11, 21)),
                _point("CafeWifi", 45.76, 4.83, created_date=date(2026, 11, 19)),
            ]
        )

        self.assertEqual(payloads[0]["geo_updated"], "2026-11-21")

    def test_keeps_missing_country_as_none(self):
        payloads = build_ssid_geo_payloads([_point("CafeWifi", 48.85, 2.35, None)])

        self.assertEqual(payloads[0]["geo"], [{"lat": 48.85, "lon": 2.35, "cc": None}])


if __name__ == "__main__":
    unittest.main()
