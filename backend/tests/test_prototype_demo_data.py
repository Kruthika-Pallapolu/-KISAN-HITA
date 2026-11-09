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
from backend.app.services.prototype_demo_service import weather


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

    def test_weather_demo_endpoints_populate_requested_districts_without_live_provider(self):
        cases = [
            ("Nellore", "Andhra Pradesh"),
            ("Guntur", "Andhra Pradesh"),
            ("Hyderabad", "Telangana"),
            ("Karnal", "Haryana"),
        ]
        client = self.guest_client()
        with patch("backend.app.services.weather_service.WeatherService._resolve_district", side_effect=AssertionError("demo must not geocode")):
            for district, state in cases:
                response = client.get("/api/weather/current", params={"district": district, "state": state, "language": "en"})
                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                self.assertEqual((payload["district"], payload["state"]), (district, state))
                self.assertIn("DEMO DATA", payload["source"])
                self.assertFalse(payload["is_official_alert"])
                self.assertGreaterEqual(payload["temperature"], 15)
                self.assertGreaterEqual(payload["humidity"], 0)
                self.assertIsNotNone(payload["rainfall_mm"])
                self.assertEqual(len(payload["forecast"]), 7)

        first = client.get("/api/weather/current", params={"district": "Nellore", "state": "Andhra Pradesh"}).json()
        again = client.get("/api/weather/current", params={"district": "Nellore", "state": "Andhra Pradesh"}).json()
        self.assertEqual(first["temperature"], again["temperature"])
        self.assertEqual(first["forecast"], again["forecast"])

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

    def test_every_directory_district_validates_for_weather_demo(self):
        directory = json.loads(DIRECTORY.read_text(encoding="utf-8"))
        states = {item["code"]: item["name"] for item in directory["states"]}
        self.assertEqual(len(directory["districts"]), 784)
        for item in directory["districts"]:
            state = states[item["stateCode"]]
            district = item["name"]
            weather_result = weather(district, state, "en")
            self.assertEqual((weather_result.district, weather_result.state), (district, state))
            self.assertEqual(len(weather_result.forecast), 7)


if __name__ == "__main__":
    unittest.main()
