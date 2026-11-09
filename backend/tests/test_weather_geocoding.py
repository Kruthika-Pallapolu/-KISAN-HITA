import json
import unittest
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch

import httpx

from app.services.weather_service import (
    WeatherService, WeatherCoverageUnavailable, WeatherGeocodingUnavailable,
    WeatherProviderUnavailable,
)


DIRECTORY = json.loads((Path(__file__).resolve().parents[2] / "frontend/src/data/indiaAdminLgd.json").read_text())
OPEN_METEO_DATA = {
    "current": {"temperature_2m": 29.5, "relative_humidity_2m": 61, "apparent_temperature": 31.0,
                "precipitation": 0, "weather_code": 2, "wind_speed_10m": 8.0},
    "daily": {"time": ["2026-11-08"] * 7, "weather_code": [2] * 7,
              "temperature_2m_max": [33] * 7, "temperature_2m_min": [22] * 7,
              "precipitation_probability_max": [10] * 7},
}


def boundary(district, state, lat=15.0, lon=78.0, country="in", field="state_district"):
    return {
        "lat": str(lat), "lon": str(lon), "category": "boundary", "type": "administrative",
        "name": district, "address": {"country_code": country, "state": state, field: district},
    }


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data, self.status_code = data, status_code

    def json(self):
        return self.data


class TestWeatherDirectoryAndGeocoding(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        WeatherService._geocode_cache.clear()

    async def _live_mock(self, district, state, result=None, forecast=OPEN_METEO_DATA):
        calls = []

        async def get(_client, url, params=None):
            calls.append((url, params or {}))
            if "nominatim.openstreetmap.org/search" in url:
                return FakeResponse(result if result is not None else [boundary(district, state)])
            return FakeResponse(forecast)

        with patch("httpx.AsyncClient.get", new=get):
            weather = await WeatherService.get_district_weather(district, state, "en")
        return weather, calls

    def test_all_784_entries_link_to_one_known_state_and_have_canonical_names(self):
        state_codes = {state["code"] for state in DIRECTORY["states"]}
        self.assertEqual(len(DIRECTORY["districts"]), 784)
        self.assertEqual(len(DIRECTORY["states"]), 36)
        self.assertTrue(all(d["stateCode"] in state_codes and d["name"].strip() for d in DIRECTORY["districts"]))

    async def test_required_state_district_combinations(self):
        valid = [
            ("Nellore", "Andhra Pradesh", 14.44, 79.98),
            ("Guntur", "Andhra Pradesh", 16.30, 80.43),
            ("Hyderabad", "Telangana", 17.38, 78.48),
            ("Karnal", "Haryana", 29.68, 76.99),
            ("Aurangabad", "Bihar", 24.75, 84.37),
            ("Chhatrapati Sambhajinagar", "Maharashtra", 19.88, 75.34),
        ]
        for district, state, lat, lon in valid:
            with self.subTest(state=state, district=district):
                result_name = "Aurangabad" if district == "Chhatrapati Sambhajinagar" else district
                result = [boundary(result_name, state, lat, lon, field="county")]
                weather, calls = await self._live_mock(district, state, result)
                self.assertEqual((weather.district, weather.state), (district, state))
                self.assertEqual(weather.source.split(".")[0], "Open-Meteo")
                self.assertIn("Nominatim", weather.coordinate_source)
                params = parse_qs(urlparse(calls[-1][0]).query)
                self.assertAlmostEqual(float(params["latitude"][0]), lat)
                self.assertAlmostEqual(float(params["longitude"][0]), lon)

    async def test_invalid_combinations_rejected_before_geocoding(self):
        for district, state in [("Hyderabad", "Andhra Pradesh"), ("Nellore", "Haryana")]:
            with self.subTest(state=state, district=district):
                with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=AssertionError("geocoder must not be called"))):
                    with self.assertRaisesRegex(ValueError, "not a district in"):
                        await WeatherService.get_district_weather(district, state)

    async def test_duplicate_name_requires_state_and_then_resolves_state_scoped_entry(self):
        grouped = defaultdict(list)
        for district in DIRECTORY["districts"]:
            grouped[district["name"].casefold()].append(district)
        duplicated = next(items for items in grouped.values() if len({item["stateCode"] for item in items}) > 1)
        name = duplicated[0]["name"]
        with self.assertRaisesRegex(ValueError, "Select a state"):
            WeatherService._canonical_location(name, None)
        state = next(s["name"] for s in DIRECTORY["states"] if s["code"] == duplicated[0]["stateCode"])
        selected_state, selected_district = WeatherService._canonical_location(name, state)
        self.assertEqual(selected_state["name"], state)
        self.assertEqual(selected_district["name"], name)

    async def test_renamed_and_frontend_aliases_resolve_to_canonical_district(self):
        state, district = WeatherService._canonical_location("Sri Potti Sriramulu Nellore", "Andhra Pradesh")
        self.assertEqual((state["name"], district["name"]), ("Andhra Pradesh", "Nellore"))
        state, district = WeatherService._canonical_location("Aurangabad", "Maharashtra")
        self.assertEqual((state["name"], district["name"]), ("Maharashtra", "Chhatrapati Sambhajinagar"))
        state, district = WeatherService._canonical_location("Aurangabad", "Bihar")
        self.assertEqual((state["name"], district["name"]), ("Bihar", "Aurangabad"))

    async def test_geocoder_checks_state_and_administrative_fields_without_wrong_state_acceptance(self):
        wrong = boundary("Karnal", "Punjab", 30.0, 76.0)
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse([wrong]))):
            with self.assertRaises(WeatherCoverageUnavailable):
                await WeatherService._resolve_district("Karnal", "Haryana")

    async def test_geocoder_timeout_and_no_match_have_distinct_failures(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.TimeoutException("slow"))):
            with self.assertRaises(WeatherGeocodingUnavailable):
                await WeatherService._resolve_district("Karnal", "Haryana")
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse([]))):
            with self.assertRaises(WeatherCoverageUnavailable):
                await WeatherService._resolve_district("Karnal", "Haryana")

    async def test_open_meteo_network_failure_is_distinct(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.ConnectError("offline"))):
            with self.assertRaises(WeatherProviderUnavailable):
                await WeatherService._fetch_forecast(29.68, 76.99, "Karnal", "Haryana", "en")

    async def test_verified_coordinates_are_cached_with_provenance(self):
        result = [boundary("Nellore", "Andhra Pradesh", 14.44, 79.98)]
        _, calls = await self._live_mock("Nellore", "Andhra Pradesh", result)
        self.assertTrue(any("nominatim.openstreetmap.org/search" in call[0] for call in calls))
        cache = WeatherService._geocode_cache[("nellore", "andhra pradesh")]
        self.assertIn("Nominatim administrative boundary", cache[5])
        before = WeatherService._geocode_cache.copy()

        async def forecast_only(_client, url, params=None):
            self.assertIn("api.open-meteo.com", url)
            return FakeResponse(OPEN_METEO_DATA)

        with patch("httpx.AsyncClient.get", new=forecast_only):
            await WeatherService.get_district_weather("Nellore", "Andhra Pradesh")
        self.assertEqual(before, WeatherService._geocode_cache)

