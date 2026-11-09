import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.main import app



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

    def test_market_prices_work_from_local_illustrative_data_without_credentials(self):
        client = self.guest_client()
        response = client.get("/api/market-prices/search", params={"commodity": "Cotton", "district": "Nellore", "state": "Andhra Pradesh"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["is_live_api"])
        self.assertEqual(payload["data_type"], "illustrative")
        self.assertTrue(payload["records"])
        self.assertIn("DEMO DATA", payload["disclaimer"])




if __name__ == "__main__":
    unittest.main()
