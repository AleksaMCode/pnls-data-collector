import unittest

from ssid_geo_mapper.geo.reducer import haversine, reduce_locations


class TestHaversine(unittest.TestCase):
    def test_returns_zero_for_identical_coordinates(self):
        self.assertAlmostEqual(haversine(46.2044, 6.1432, 46.2044, 6.1432), 0.0, places=9)

    def test_is_symmetric(self):
        a_to_b = haversine(46.2044, 6.1432, 47.3769, 8.5417)
        b_to_a = haversine(47.3769, 8.5417, 46.2044, 6.1432)
        self.assertAlmostEqual(a_to_b, b_to_a, places=9)

    def test_matches_known_distance_approximately(self):
        # London (51.5074, -0.1278) to Paris (48.8566, 2.3522) is ~343 km.
        distance_km = haversine(51.5074, -0.1278, 48.8566, 2.3522)
        self.assertAlmostEqual(distance_km, 343.0, delta=3.0)


class TestReduceLocations(unittest.TestCase):
    def test_returns_empty_list_when_input_is_empty(self):
        self.assertEqual(reduce_locations([]), [])

    def test_deduplicates_exact_same_coordinates(self):
        locations = [
            {"ssid": "MyWifi", "lat": 46.2044, "long": 6.1432, "alpha2": "CH"},
            {"ssid": "MyWifi", "lat": 46.2044, "long": 6.1432, "alpha2": "CH"},
            {"ssid": "MyWifi", "lat": 47.3769, "long": 8.5417, "alpha2": "CH"},
        ]

        result = reduce_locations(locations)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["lat"], 46.2044)
        self.assertEqual(result[0]["long"], 6.1432)
        self.assertEqual(result[1]["lat"], 47.3769)
        self.assertEqual(result[1]["long"], 8.5417)

    def test_filters_points_below_threshold_and_keeps_far_points(self):
        locations = [
            {"ssid": "MyWifi", "lat": 46.2000, "long": 6.1400, "alpha2": "CH"},
            # ~11 km from first point -> below default threshold (27 km), should be filtered
            {"ssid": "MyWifi", "lat": 46.3000, "long": 6.1400, "alpha2": "CH"},
            # ~111 km from first point -> above threshold, should be kept
            {"ssid": "MyWifi", "lat": 47.2000, "long": 6.1400, "alpha2": "CH"},
        ]

        result = reduce_locations(locations)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["lat"], 46.2)
        self.assertEqual(result[1]["lat"], 47.2)


if __name__ == "__main__":
    unittest.main()
