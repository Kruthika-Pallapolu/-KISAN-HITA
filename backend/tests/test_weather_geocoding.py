import json
import math
import os
import subprocess
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from app.config import settings
from app.services.weather_service import (
    WeatherCoverageUnavailable,
    WeatherGeocodingUnavailable,
    WeatherLocationAmbiguous,
    WeatherLocationNotFound,
    WeatherProviderUnavailable,
    WeatherService,
)

DIRECTORY = json.loads((Path(__file__).resolve().parents[2] / "frontend/src/data/indiaAdminLgd.json").read_text())


def forecast_payload(name="Nellore", region="Andhra Pradesh", country="India"):
    return {
        "location": {"name": name, "region": region, "country": country, "lat": 14.44, "lon": 79.98},
        "current": {
            "temp_c": 29.5, "feelslike_c": 31.0, "humidity": 61,
            "wind_kph": 8.0, "wind_dir": "SW", "vis_km": 10.0, "precip_mm": 0.0,
            "condition": {"text": "Partly cloudy", "code": 1003, "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png"},
        },
        "forecast": {"forecastday": [
            {"date": "2026-11-09", "day": {
                "maxtemp_c": 33, "mintemp_c": 22, "daily_chance_of_rain": 10,
                "condition": {"text": "Partly cloudy", "code": 1003, "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png"},
            }},
            {"date": "2026-11-10", "day": {
                "maxtemp_c": 32, "mintemp_c": 21, "daily_chance_of_rain": 20,
                "condition": {"text": "Cloudy", "code": 1006, "icon": "//cdn.weatherapi.com/weather/64x64/day/119.png"},
            }},
            {"date": "2026-11-11", "day": {
                "maxtemp_c": 31, "mintemp_c": 22, "daily_chance_of_rain": 15,
                "condition": {"text": "Sunny", "code": 1000, "icon": "//cdn.weatherapi.com/weather/64x64/day/113.png"},
            }},
        ]},
    }


def search_result(name="Nellore", region="Andhra Pradesh", country="India", lat=14.44, lon=79.98):
    return {"name": name, "region": region, "country": country, "lat": lat, "lon": lon, "id": 1}


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data, self.status_code = data, status_code

    def json(self):
        return self.data


class TestWeatherDirectoryAndWeatherApi(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        WeatherService._geocode_cache.clear()
        WeatherService._forecast_cache.clear()
        self.demo_patch = patch.object(settings, "DEMO_DATA_ENABLED", False)
        self.demo_patch.start()
        self.addCleanup(self.demo_patch.stop)
        self.key_patch = patch.object(settings, "WEATHERAPI_KEY", "offline-test-key")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)

    async def _mock_provider(self, district="Nellore", state="Andhra Pradesh", results=None, forecast=None):
        results = results if results is not None else [search_result(district, state)]
        forecast = forecast if forecast is not None else forecast_payload(district, state)
        calls = []

        async def get(_client, url, params=None):
            calls.append((url, params or {}))
            if url.endswith("/search.json"):
                return FakeResponse(results)
            return FakeResponse(forecast)

        with patch("httpx.AsyncClient.get", new=get):
            weather = await WeatherService.get_district_weather(district, state, "en")
        return weather, calls

    def test_all_directory_entries_have_canonical_state_links(self):
        state_codes = {state["code"] for state in DIRECTORY["states"]}
        self.assertEqual(len(DIRECTORY["districts"]), 784)
        self.assertEqual(len(DIRECTORY["states"]), 36)
        self.assertTrue(all(d["stateCode"] in state_codes and d["name"].strip() for d in DIRECTORY["districts"]))

    async def test_required_state_district_combinations_validate(self):
        valid = [
            ("Nellore", "Andhra Pradesh"), ("Warangal", "Telangana"),
            ("Guntur", "Andhra Pradesh"), ("Hyderabad", "Telangana"),
            ("Karnal", "Haryana"), ("Aurangabad", "Bihar"),
            ("Chhatrapati Sambhajinagar", "Maharashtra"),
        ]
        for district, state in valid:
            with self.subTest(state=state, district=district):
                selected_state, selected_district = WeatherService._canonical_location(district, state)
                self.assertEqual(selected_state["name"], state)
                self.assertEqual(selected_district["name"], district)

    async def test_invalid_state_district_combinations_are_rejected_before_requests(self):
        for district, state in [("Hyderabad", "Andhra Pradesh"), ("Nellore", "Haryana")]:
            with self.subTest(state=state, district=district):
                with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=AssertionError("provider must not be called"))):
                    with self.assertRaisesRegex(ValueError, "not a district in"):
                        await WeatherService.get_district_weather(district, state)

    async def test_duplicate_name_requires_state_and_then_state_scopes(self):
        grouped = defaultdict(list)
        for district in DIRECTORY["districts"]:
            grouped[district["name"].casefold()].append(district)
        duplicated = next(items for items in grouped.values() if len({item["stateCode"] for item in items}) > 1)
        name = duplicated[0]["name"]
        with self.assertRaisesRegex(ValueError, "Select a state"):
            WeatherService._canonical_location(name, None)
        state = next(s["name"] for s in DIRECTORY["states"] if s["code"] == duplicated[0]["stateCode"])
        self.assertEqual(WeatherService._canonical_location(name, state)[0]["name"], state)

    async def test_freeform_city_search_fetches_a_verified_real_location_forecast(self):
        cases = [
            ("Hyderabad", "Hyderabad", "Telangana", "India", 17.385, 78.4867),
            ("Chennai, Tamil Nadu, India", "Chennai", "Tamil Nadu", "India", 13.0827, 80.2707),
            ("Paris, France", "Paris", "Ile-de-France", "France", 48.8566, 2.3522),
        ]
        for query, name, region, country, lat, lon in cases:
            with self.subTest(query=query):
                payload = forecast_payload(name, region, country)
                payload["location"].update({"lat": lat, "lon": lon})
                calls = []

                async def get(_client, url, params=None):
                    calls.append((url, params or {}))
                    if url.endswith("/search.json"):
                        return FakeResponse([search_result(name, region, country, lat, lon)])
                    return FakeResponse(payload)

                with patch("httpx.AsyncClient.get", new=get):
                    result = await WeatherService.get_location_weather(query)
                self.assertEqual((result.district, result.state, result.country), (name, region, country))
                self.assertEqual(result.temperature, 29.5)
                self.assertEqual([url.rsplit("/", 1)[-1] for url, _ in calls], ["search.json", "forecast.json"])
                self.assertEqual(calls[0][1]["q"], query)
                self.assertEqual(calls[1][1]["q"], "id:1")

    async def test_bengaluru_south_query_formats_normalize_and_resolve_exact_admin_area(self):
        for query in ("karnataka/benguluru-south", "Bengaluru South, Karnataka"):
            with self.subTest(query=query):
                WeatherService._geocode_cache.clear()
                WeatherService._forecast_cache.clear()
                payload = forecast_payload("Bengaluru South", "Karnataka", "India")
                payload["location"].update({"lat": 12.8, "lon": 77.5})
                calls = []

                async def get(_client, url, params=None):
                    calls.append((url, params or {}))
                    if url.endswith("/search.json"):
                        return FakeResponse([search_result("Bengaluru South", "Karnataka", "India", 12.8, 77.5)])
                    return FakeResponse(payload)

                with patch("httpx.AsyncClient.get", new=get):
                    result = await WeatherService.get_location_weather(query)
                self.assertEqual((result.district, result.state), ("Bengaluru South", "Karnataka"))
                self.assertEqual(result.temperature, 29.5)
                self.assertEqual(calls[0][1]["q"], "Bengaluru South, Karnataka, India")
                self.assertEqual(calls[1][1]["q"], "id:1")

    async def test_bengaluru_south_never_substitutes_weatherapi_nearby_city(self):
        cases = [
            ("karnataka/benguluru-south", "Kadaba", 12.73, 75.47),
            ("Bengaluru South, Karnataka", "Bengaluru", 12.98, 77.58),
        ]
        for query, provider_name, lat, lon in cases:
            with self.subTest(query=query):
                WeatherService._geocode_cache.clear()

                async def get(_client, url, params=None):
                    if url.endswith("/search.json"):
                        return FakeResponse([search_result(provider_name, "Karnataka", "India", lat, lon)])
                    raise AssertionError("Forecast must not run for a nonmatching area")

                with patch("httpx.AsyncClient.get", new=get):
                    with self.assertRaises(WeatherLocationNotFound):
                        await WeatherService.get_location_weather(query)

    async def test_freeform_search_reports_empty_and_ambiguous_locations(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse([]))):
            with self.assertRaises(WeatherLocationNotFound):
                await WeatherService.get_location_weather("No Such Place")
        candidates = [
            search_result("Springfield", "Illinois", "United States", 39.78, -89.64),
            search_result("Springfield", "Missouri", "United States", 37.21, -93.29),
        ]
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(candidates))):
            with self.assertRaises(WeatherLocationAmbiguous):
                await WeatherService.get_location_weather("Springfield")

    async def test_freeform_search_rejects_forecast_from_different_country_or_region(self):
        selected = search_result("Hyderabad", "Telangana", "India", 17.385, 78.4867)
        for payload in (
            forecast_payload("Hyderabad", "Telangana", "Pakistan"),
            forecast_payload("Hyderabad", "Andhra Pradesh", "India"),
        ):
            payload["location"].update({"lat": 17.385, "lon": 78.4867})

            async def get(_client, url, params=None):
                return FakeResponse([selected] if url.endswith("/search.json") else payload)

            with patch("httpx.AsyncClient.get", new=get):
                with self.assertRaises(WeatherCoverageUnavailable):
                    await WeatherService.get_location_weather("Hyderabad")

    async def test_renamed_district_aliases_resolve_to_canonical_entries(self):
        self.assertEqual(WeatherService._canonical_location("Sri Potti Sriramulu Nellore", "Andhra Pradesh")[1]["name"], "Nellore")
        self.assertEqual(WeatherService._canonical_location("Aurangabad", "Maharashtra")[1]["name"], "Chhatrapati Sambhajinagar")
        self.assertEqual(WeatherService._canonical_location("Aurangabad", "Bihar")[1]["name"], "Aurangabad")

    async def test_district_search_and_forecast_use_weatherapi_and_keep_response_contract(self):
        weather, calls = await self._mock_provider()
        self.assertEqual((weather.district, weather.state), ("Nellore", "Andhra Pradesh"))
        self.assertAlmostEqual(weather.temperature, 29.5)
        self.assertAlmostEqual(weather.feels_like, 31.0)
        self.assertEqual(weather.humidity, 61)
        self.assertAlmostEqual(weather.wind_speed, 8.0)
        self.assertEqual(weather.wind_direction, "SW")
        self.assertAlmostEqual(weather.visibility_km, 10.0)
        self.assertEqual(weather.condition_code, 1003)
        self.assertEqual(weather.condition_icon_url, "https://cdn.weatherapi.com/weather/64x64/day/116.png")
        self.assertEqual(weather.rainfall_mm, 0.0)
        self.assertEqual(weather.rain_probability, 10)
        self.assertEqual(weather.forecast[0].icon, "cloud-sun")
        self.assertEqual(len(weather.forecast), 3)
        self.assertIn("WeatherAPI.com", weather.source)
        self.assertIn("WeatherAPI.com Search API", weather.coordinate_source)
        self.assertFalse(weather.is_official_alert)
        self.assertTrue(calls[0][0].endswith("/search.json"))
        self.assertEqual(calls[0][1]["q"], "Nellore, Andhra Pradesh, India")
        self.assertTrue(calls[1][0].endswith("/forecast.json"))
        self.assertEqual(calls[1][1]["q"], "14.44,79.98")
        self.assertEqual(calls[1][1]["days"], 3)
        self.assertNotIn("key", calls[0][0])
        self.assertEqual(calls[0][1]["key"], "offline-test-key")
        self.assertEqual(calls[1][1]["key"], "offline-test-key")

    async def test_wrong_country_state_or_district_search_results_are_rejected(self):
        cases = [
            search_result(country="Nepal"),
            search_result(region="Telangana"),
            search_result(name="Nearby City"),
            search_result(lat=float("nan")),
            search_result(lon=181),
            search_result(lat=0, lon=0),
        ]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse([candidate]))):
                    with self.assertRaises(WeatherCoverageUnavailable):
                        await WeatherService._resolve_district("Nellore", "Andhra Pradesh")
                self.assertNotIn(("nellore", "andhra pradesh"), WeatherService._geocode_cache)

    async def test_ambiguous_exact_district_candidates_are_rejected(self):
        results = [search_result(lat=14.4, lon=79.9), search_result(lat=14.5, lon=80.0)]
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(results))):
            with self.assertRaisesRegex(WeatherCoverageUnavailable, "ambiguous"):
                await WeatherService._resolve_district("Nellore", "Andhra Pradesh")
        self.assertNotIn(("nellore", "andhra pradesh"), WeatherService._geocode_cache)

    async def test_geocode_timeout_and_malformed_search_are_reported(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.TimeoutException("private request details"))):
            with self.assertRaises(WeatherGeocodingUnavailable):
                await WeatherService._resolve_district("Nellore", "Andhra Pradesh")
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse({"bad": "shape"}))):
            with self.assertRaises(WeatherGeocodingUnavailable):
                await WeatherService._resolve_district("Nellore", "Andhra Pradesh")

    async def test_search_and_forecast_cache_reuse(self):
        calls = []

        async def get(_client, url, params=None):
            calls.append(url)
            return FakeResponse([search_result()] if url.endswith("search.json") else forecast_payload())

        with patch("httpx.AsyncClient.get", new=get):
            first = await WeatherService.get_district_weather("Nellore", "Andhra Pradesh")
            second = await WeatherService.get_district_weather("Nellore", "Andhra Pradesh")
        self.assertEqual(first, second)
        self.assertEqual(calls.count("https://api.weatherapi.com/v1/search.json"), 1)
        self.assertEqual(calls.count("https://api.weatherapi.com/v1/forecast.json"), 1)
        self.assertIn("WeatherAPI.com Search API", WeatherService._geocode_cache[("nellore", "andhra pradesh")][5])

    async def test_coordinate_route_uses_provider_coordinates_directly_without_geocoding(self):
        calls = []

        async def get(_client, url, params=None):
            calls.append((url, params or {}))
            return FakeResponse({**forecast_payload("Kurnool", "Andhra Pradesh"), "location": {"name": "Kurnool", "region": "Andhra Pradesh", "country": "India", "lat": 15.8281, "lon": 78.0373}})

        with patch("httpx.AsyncClient.get", new=get):
            weather = await WeatherService.get_coordinate_weather(15.8281, 78.0373, "te")
        self.assertEqual((weather.district, weather.state), ("Kurnool", "Andhra Pradesh"))
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][0].endswith("/forecast.json"))
        self.assertEqual(calls[0][1]["q"], "15.8281,78.0373")
        self.assertEqual(calls[0][1]["lang"], "te")

    async def test_invalid_coordinates_are_rejected_before_provider_request(self):
        for lat, lon in [(91, 0), (0, 181), (math.inf, 1), ("bad", 1)]:
            with self.subTest(lat=lat, lon=lon):
                with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=AssertionError("provider must not be called"))):
                    with self.assertRaises(ValueError):
                        await WeatherService.get_coordinate_weather(lat, lon)

    async def test_coordinate_response_must_verify_india_and_state(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(forecast_payload(country="Nepal")))):
            with self.assertRaisesRegex(ValueError, "India"):
                await WeatherService.get_coordinate_weather(14.4, 79.9)
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(forecast_payload(region="Unknown Region")))):
            with self.assertRaises(WeatherCoverageUnavailable):
                await WeatherService.get_coordinate_weather(14.4, 79.9)

    async def test_coordinate_provider_must_return_the_requested_location(self):
        payload = forecast_payload()
        payload["location"].update({"lat": 20.0, "lon": 79.98})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(payload))):
            with self.assertRaisesRegex(WeatherCoverageUnavailable, "different location"):
                await WeatherService.get_coordinate_weather(14.44, 79.98)

    async def test_weatherapi_environment_name_loads_without_legacy_variable(self):
        env = os.environ.copy()
        env.pop("WEATHER_API_KEY", None)
        env["WEATHERAPI_KEY"] = "configuration-test-value"
        script = (
            "from app.config import settings; "
            "assert settings.WEATHERAPI_KEY == 'configuration-test-value'; "
            "assert not hasattr(settings, 'WEATHER_API_KEY')"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    async def test_missing_key_makes_no_outbound_request(self):
        with patch.object(settings, "WEATHERAPI_KEY", ""), patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=AssertionError("must not make request"))) as request:
            with self.assertRaisesRegex(WeatherProviderUnavailable, "WEATHERAPI_KEY"):
                await WeatherService._fetch_forecast(14.4, 79.9, "Nellore", "Andhra Pradesh", "en")
            request.assert_not_awaited()

    async def test_provider_errors_never_log_or_return_api_key(self):
        secret = "offline-secret-that-must-not-leak"
        with patch.object(settings, "WEATHERAPI_KEY", secret), \
             patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse({"error": {"code": 2006}}, 401))), \
             self.assertLogs("weather_service", level="WARNING") as captured:
            with self.assertRaises(WeatherProviderUnavailable) as raised:
                await WeatherService._fetch_forecast(14.4, 79.9, "Nellore", "Andhra Pradesh", "en")
        self.assertNotIn(secret, str(raised.exception))
        self.assertNotIn(secret, "\n".join(captured.output))

    async def test_weatherapi_requests_use_the_configured_key(self):
        weather, calls = await self._mock_provider()
        self.assertTrue(weather)
        self.assertTrue(calls)
        self.assertTrue(all(params.get("key") == "offline-test-key" for _, params in calls))

    async def test_http_errors_timeouts_and_network_errors_are_safe(self):
        cases = [
            (FakeResponse({"error": {"code": 2006}}, 401), "rejected the configured API key"),
            (FakeResponse({}, 503), "HTTP 503"),
        ]
        for response, message in cases:
            with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
                with self.assertRaisesRegex(WeatherProviderUnavailable, message):
                    await WeatherService._fetch_forecast(14.4, 79.9, "Nellore", "Andhra Pradesh", "en")
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.TimeoutException("do not expose"))):
            with self.assertRaisesRegex(WeatherProviderUnavailable, "timed out") as error:
                await WeatherService._fetch_forecast(14.4, 79.9, "Nellore", "Andhra Pradesh", "en")
            self.assertNotIn("do not expose", str(error.exception))
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.ConnectError("do not expose"))):
            with self.assertRaisesRegex(WeatherProviderUnavailable, "could not be reached") as error:
                await WeatherService._fetch_forecast(14.4, 79.9, "Nellore", "Andhra Pradesh", "en")
            self.assertNotIn("do not expose", str(error.exception))

    async def test_malformed_forecasts_fail_closed_without_caching(self):
        cases = [
            {},
            {**forecast_payload(), "current": {"temp_c": "bad"}},
            {**forecast_payload(), "forecast": {"forecastday": []}},
        ]
        for payload in cases:
            WeatherService._forecast_cache.clear()
            with self.subTest(payload=payload):
                with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(payload))):
                    with self.assertRaises(WeatherProviderUnavailable):
                        await WeatherService._fetch_forecast(14.44, 79.98, "Nellore", "Andhra Pradesh", "en")
                self.assertFalse(WeatherService._forecast_cache)

    async def test_missing_wind_visibility_or_untrusted_icon_fails_closed(self):
        payload = forecast_payload()
        payload["current"].pop("wind_dir")
        cases = [payload]
        bad_icon = forecast_payload()
        bad_icon["current"]["condition"]["icon"] = "https://attacker.example/weather/icon.png"
        cases.append(bad_icon)
        for candidate in cases:
            with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(candidate))):
                with self.assertRaises(WeatherProviderUnavailable):
                    await WeatherService.get_coordinate_weather(14.44, 79.98)

    async def test_forecast_cache_is_scoped_to_coordinates_and_location(self):
        WeatherService._forecast_cache.clear()
        calls = []

        async def get(_client, url, params=None):
            calls.append(params["q"])
            name = "Warangal" if params["q"].startswith("17.87") else "Nellore"
            state = "Telangana" if name == "Warangal" else "Andhra Pradesh"
            payload = forecast_payload(name, state)
            payload["location"].update({"lat": float(params["q"].split(",")[0]), "lon": float(params["q"].split(",")[1])})
            return FakeResponse(payload)

        with patch("httpx.AsyncClient.get", new=get):
            nellore = await WeatherService._fetch_forecast(14.44, 79.98, "Nellore", "Andhra Pradesh", "en", expected_state="Andhra Pradesh")
            warangal = await WeatherService._fetch_forecast(17.87, 79.80, "Warangal", "Telangana", "en", expected_state="Telangana")
            cached = await WeatherService._fetch_forecast(14.44, 79.98, "Nellore", "Andhra Pradesh", "en", expected_state="Andhra Pradesh")
        self.assertEqual((nellore.temperature, warangal.temperature), (29.5, 29.5))
        self.assertEqual(cached, nellore)
        self.assertEqual(len(calls), 2)

    async def test_forecast_cache_does_not_merge_nearby_coordinates(self):
        WeatherService._forecast_cache.clear()
        calls = []

        async def get(_client, _url, params=None):
            calls.append(params["q"])
            lat, lon = (float(value) for value in params["q"].split(","))
            payload = forecast_payload()
            payload["location"].update({"lat": lat, "lon": lon})
            return FakeResponse(payload)

        with patch("httpx.AsyncClient.get", new=get):
            await WeatherService.get_coordinate_weather(14.4401, 79.9801)
            await WeatherService.get_coordinate_weather(14.4449, 79.9849)
        self.assertEqual(len(calls), 2)

    async def test_provider_location_cannot_silently_substitute_district(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=FakeResponse(forecast_payload("Guntur", "Andhra Pradesh")))):
            with self.assertRaisesRegex(WeatherCoverageUnavailable, "different district"):
                await WeatherService._fetch_forecast(
                    14.44, 79.98, "Nellore", "Andhra Pradesh", "en",
                    expected_state="Andhra Pradesh",
                    expected_district=WeatherService._canonical_location("Nellore", "Andhra Pradesh")[1],
                )


if __name__ == "__main__":
    unittest.main()
