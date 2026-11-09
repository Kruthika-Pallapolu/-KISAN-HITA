import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.main import app
from backend.app.services.weather_service import WeatherService


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "frontend" / "src" / "data" / "indiaAdminLgd.json"


class FakeResponse:
    def __init__(self, data):
        self.data = data
        self.status_code = 200

    def json(self):
        return self.data


def search_result(name, region, country, lat, lon):
    return {"name": name, "region": region, "country": country, "lat": lat, "lon": lon}


def forecast_payload(name, region, country):
    icon = "//cdn.weatherapi.com/weather/64x64/day/116.png"
    return {
        "location": {"name": name, "region": region, "country": country, "lat": 0, "lon": 0},
        "current": {
            "temp_c": 29.5, "feelslike_c": 31, "humidity": 61, "wind_kph": 8,
            "wind_dir": "SW", "vis_km": 10, "precip_mm": 0,
            "condition": {"text": "Partly cloudy", "code": 1003, "icon": icon},
        },
        "forecast": {"forecastday": [{"date": "2026-11-10", "day": {
            "maxtemp_c": 32, "mintemp_c": 21, "daily_chance_of_rain": 20,
            "condition": {"text": "Cloudy", "code": 1006, "icon": icon},
        }}]},
    }


class PrototypeDemoDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="kisan-demo-test-")
        self.old_database = settings.DATABASE_PATH
        self.old_demo_mode = settings.DEMO_DATA_ENABLED
        settings.DATABASE_PATH = os.path.join(self.temp_dir.name, "demo-test.sqlite3")
        settings.DEMO_DATA_ENABLED = True
        init_db()

    def tearDown(self):
        settings.DATABASE_PATH = self.old_database
        settings.DEMO_DATA_ENABLED = self.old_demo_mode
        self.temp_dir.cleanup()

    def guest_client(self):
        client = TestClient(app)
        created = client.post("/api/auth/guest")
        self.assertEqual(created.status_code, 200, created.text)
        return client

    def test_weather_never_returns_synthetic_data_when_live_key_is_missing(self):
        client = self.guest_client()
        with patch.object(settings, "WEATHERAPI_KEY", ""), patch("httpx.AsyncClient.get", side_effect=AssertionError("missing key must not make a request")):
            district = client.get("/api/weather/current", params={"district": "Nellore", "state": "Andhra Pradesh", "language": "en"})
            coordinates = client.post("/api/weather/current/coordinates", json={
                "latitude": 14.44, "longitude": 79.98, "language": "en",
            })
        for response in (district, coordinates):
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"]["code"], "weather_configuration_missing")
            self.assertIn("WEATHERAPI_KEY", response.json()["detail"]["message"])

    def test_weather_search_endpoint_returns_provider_location_and_forecast(self):
        client = self.guest_client()
        payload = forecast_payload("Hyderabad", "Telangana", "India")
        payload["location"].update({"lat": 17.385, "lon": 78.4867})

        async def provider_get(_client, url, params=None):
            if url.endswith("/search.json"):
                return FakeResponse([search_result("Hyderabad", "Telangana", "India", 17.385, 78.4867)])
            return FakeResponse(payload)

        with patch.object(settings, "WEATHERAPI_KEY", "offline-test-key"), patch("httpx.AsyncClient.get", new=provider_get):
            response = client.get("/api/weather/search", params={"query": "Hyderabad", "language": "en"})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual((result["district"], result["state"], result["country"]), ("Hyderabad", "Telangana", "India"))
        self.assertEqual(result["temperature"], 29.5)

    def test_weather_search_endpoint_has_distinct_no_result_and_ambiguous_errors(self):
        client = self.guest_client()
        async def no_results(_client, _url, params=None):
            return FakeResponse([])
        with patch.object(settings, "WEATHERAPI_KEY", "offline-test-key"), patch("httpx.AsyncClient.get", new=no_results):
            response = client.get("/api/weather/search", params={"query": "No Such Place"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "weather_location_not_found")

    def test_market_prices_work_from_local_illustrative_data_without_credentials(self):
        client = self.guest_client()
        response = client.get("/api/market-prices/search", params={"commodity": "Cotton", "district": "Nellore", "state": "Andhra Pradesh"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["is_live_api"])
        self.assertEqual(payload["data_type"], "illustrative")
        self.assertTrue(payload["records"])
        self.assertIn("DEMO DATA", payload["disclaimer"])


    def test_mismatched_state_district_is_rejected(self):
        client = self.guest_client()
        weather_response = client.get("/api/weather/current", params={"district": "Hyderabad", "state": "Andhra Pradesh"})
        self.assertEqual(weather_response.status_code, 422)

    def test_every_directory_district_passes_canonical_membership_validation(self):
        directory = json.loads(DIRECTORY.read_text(encoding="utf-8"))
        states = {item["code"]: item["name"] for item in directory["states"]}
        self.assertEqual(len(directory["districts"]), 784)
        for item in directory["districts"]:
            state = states[item["stateCode"]]
            district = item["name"]
            selected_state, selected_district = WeatherService._canonical_location(district, state)
            self.assertEqual((selected_district["name"], selected_state["name"]), (district, state))


if __name__ == "__main__":
    unittest.main()
