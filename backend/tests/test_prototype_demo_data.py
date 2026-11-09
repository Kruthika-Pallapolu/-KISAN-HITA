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
