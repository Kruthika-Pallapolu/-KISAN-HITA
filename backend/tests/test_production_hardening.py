import unittest
import asyncio
import base64
import os
import sys
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
from auth_helpers import authenticated_client

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.config import settings
from app.database import check_storage_writable
from app.models.schemas import CropHealthRequest, CropRecommendation, MarketPriceResponse
from app.services.crop_service import CropAdvisorService
from app.services.market_service import MarketPriceService

class TestProductionHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = authenticated_client(app)

    def test_readiness_endpoint_healthy(self):
        """Verifies /api/ready returns 200 with connected DB and writable storage."""
        res = self.client.get("/api/ready")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["database"], "connected")
        self.assertEqual(data["storage"], "writable")
        self.assertIn("gemini_configured", data)
        self.assertIn("timestamp", data)
        self.assertEqual(data["app"], "Kisan Hita")

    def test_storage_probe_preserves_existing_fixed_name_file(self):
        """Readiness must not overwrite or delete another file in the DB directory."""
        old_path = settings.DATABASE_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                settings.DATABASE_PATH = os.path.join(directory, "test.sqlite3")
                sentinel = os.path.join(directory, ".healthcheck_write_test")
                with open(sentinel, "w", encoding="utf-8") as existing:
                    existing.write("keep this file")

                self.assertTrue(check_storage_writable())
                with open(sentinel, encoding="utf-8") as existing:
                    self.assertEqual(existing.read(), "keep this file")
                self.assertEqual(
                    [name for name in os.listdir(directory) if name.startswith(".healthcheck_write_test_")],
                    [],
                )
        finally:
            settings.DATABASE_PATH = old_path

    def test_cors_configuration_parsing(self):
        """Verifies allowed_origins_list splits comma-separated strings."""
        old_val = settings.ALLOWED_ORIGINS
        try:
            settings.ALLOWED_ORIGINS = "https://kisan-hita.app, http://localhost:5173"
            self.assertEqual(settings.allowed_origins_list, [
                "https://kisan-hita.app", "http://localhost:5173",
                "http://192.168.29.3:5173", "http://192.168.29.52:5173",
            ])
            
            settings.ALLOWED_ORIGINS = "*"
            self.assertNotIn("*", settings.allowed_origins_list)
            self.assertIn("http://192.168.29.3:5173", settings.allowed_origins_list)
            self.assertIn("http://192.168.29.52:5173", settings.allowed_origins_list)
        finally:
            settings.ALLOWED_ORIGINS = old_val

    def test_crop_health_input_validation(self):
        """Verifies schema validation catches empty crop names or symptoms."""
        # Empty crop name
        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "   ",
            "symptoms": "Yellow leaves",
            "language": "en"
        })
        self.assertEqual(res.status_code, 422)

        # Empty symptoms
        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "   ",
            "language": "en"
        })
        self.assertEqual(res.status_code, 422)

    def test_crop_health_oversized_image_rejection(self):
        """Verifies image payload exceeding 14MB base64 (~10MB raw) is rejected with 422."""
        # Create oversized payload (> 14MB)
        oversized = "a" * (14 * 1024 * 1024 + 10)
        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "Yellow leaves",
            "image_base64": oversized,
            "language": "en"
        })
        self.assertEqual(res.status_code, 422)
        err = res.json()["detail"][0]["msg"]
        self.assertIn("10MB", err)

    def test_crop_advisor_provenance_fields(self):
        """Verifies crop recommendations include publication_date and applicable_regions."""
        res = CropAdvisorService.get_recommendations(
            soil="Black Cotton Soil",
            water="Good irrigation",
            season="Kharif (Monsoon)",
            district="Warangal"
        )
        self.assertGreater(len(res.recommendations), 0)
        self.assertTrue(res.recommendations[0].publication_date)
        self.assertTrue(res.recommendations[0].applicable_regions)
        self.assertIn("demo", res.disclaimer.lower())

    def test_market_price_provenance_and_live_flag(self):
        res = asyncio.run(MarketPriceService.get_market_prices(commodity="Chilli", district="Warangal"))
        self.assertTrue(res.records)
        self.assertIn("Synthetic reference", res.data_provenance)
        self.assertFalse(res.is_live_api)
        self.assertEqual(res.data_type, "illustrative")
        self.assertIsNone(res.source_url)


    def test_market_rejects_unsupported_language(self):
        market = self.client.get("/api/market-prices/search?commodity=Chilli&language=fr")
        self.assertEqual(market.status_code, 422)
