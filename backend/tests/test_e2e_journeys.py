import unittest
import asyncio
import base64
import os
import sys
import tempfile
import speech_recognition as sr
from unittest.mock import patch
from fastapi.testclient import TestClient
from auth_helpers import authenticated_client

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.config import settings
from app.database import init_db
from app.services.gnani_voice import generate_mock_wav
from app.services.market_service import MarketPriceService

class TestKisanHitaE2EJourneys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_path = settings.DATABASE_PATH
        cls.test_db_dir = tempfile.TemporaryDirectory()
        settings.DATABASE_PATH = os.path.join(cls.test_db_dir.name, "e2e.sqlite")
        init_db()
        cls.client = authenticated_client(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        settings.DATABASE_PATH = cls.previous_db_path
        cls.test_db_dir.cleanup()

    def test_health_endpoint(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["app"], "Kisan Hita")
        self.assertFalse(data["gnani_live_enabled"])

    def test_journey_2_crop_advisor_black_soil_kharif(self):
        """
        Farmer navigates to Choose My Crop and supplies Black Cotton Soil,
        Good Irrigation, Kharif season in Warangal.
        System provides clearly labeled demo reference recommendations.
        """
        payload = {
            "soil_type": "Black Cotton Soil",
            "water_availability": "Good irrigation",
            "growing_season": "Kharif (Monsoon)",
            "district": "Warangal",
            "state": "Telangana",
            "language": "en"
        }
        res = self.client.post("/api/crop-advisor/recommend", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertGreater(len(data["recommendations"]), 0)
        self.assertEqual(data["total_found"], len(data["recommendations"]))
        self.assertIn("DEMO", data["disclaimer"])
        self.assertIn("not scientifically verified", data["disclaimer"])

    def test_crop_advisor_nellore_black_soil_kharif_demo(self):
        """Exact reported request, with Nellore's correct state, returns demo matches."""
        response = self.client.post("/api/crop-advisor/recommend", json={
            "district": "Nellore",
            "state": "Andhra Pradesh",
            "soil_type": "Black Cotton Soil",
            "water_availability": "Good irrigation",
            "growing_season": "Kharif (Monsoon)",
            "language": "en",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_found"], 3)
        self.assertEqual(len(data["recommendations"]), 3)
        self.assertIn("DEMO", data["disclaimer"])
        self.assertIn("not scientifically verified", data["disclaimer"])

    def test_crop_advisor_flags_conflicting_nellore_state(self):
        """A mismatched state is called out and cannot add state-region scoring."""
        response = self.client.post("/api/crop-advisor/recommend", json={
            "district": "Nellore",
            "state": "Telangana",
            "soil_type": "Black Cotton Soil",
            "water_availability": "Good irrigation",
            "growing_season": "Kharif (Monsoon)",
            "language": "en",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total_found"], 0)
        self.assertIn("Nellore is associated with Andhra Pradesh", data["disclaimer"])
        self.assertIn("request specified Telangana", data["disclaimer"])
        self.assertIn("Krishi Vigyan Kendra", data["disclaimer"])

    def test_journey_3_crop_health_yellow_leaves_symptom(self):
        """
        Farmer reports yellowing leaves on cotton crop with photo.
        System provides honest, safety-first evaluation without fake disease confidences
        or unverified chemical pesticide prescriptions.
        """
        payload = {
            "crop_name": "Cotton",
            "symptoms": "Lower leaves turning yellow with brown spots",
            "onset_days": "2-3 days ago",
            "affected_spread": "Few scattered plants",
            "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "language": "en"
        }
        res = self.client.post("/api/crop-health/diagnose", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertEqual(data["crop_name"], "Cotton")
        self.assertTrue(data["has_image"])
        self.assertGreater(len(data["potential_factors"]), 0)
        self.assertGreater(len(data["cultural_management_steps"]), 0)
        self.assertIn("Safety Notice", data["safety_notice"])
        self.assertIn("Never apply unverified synthetic chemical pesticides", data["safety_notice"])
        self.assertIn("1800-180-1551", data["extension_contact"])

    def test_journey_4_market_prices_chilli_mandi(self):
        """Market display uses local illustrative district references, not claimed mandi records."""
        res = self.client.get("/api/market-prices/search?commodity=Chilli&state=Andhra%20Pradesh&district=Guntur")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(len(data["records"]), 0)
        self.assertEqual(data["total_count"], len(data["records"]))
        self.assertFalse(data["is_live_api"])
        self.assertEqual(data["data_type"], "illustrative")
        self.assertIn("DEMO DATA", data["disclaimer"])
        self.assertEqual(data["records"][0]["unit"], "kg")
        self.assertIsNone(data["records"][0]["market"])


    def test_journey_5_settings_profile_persistence(self):
        """
        Farmer updates preferred assistant name and district.
        Preferences are persisted and reflected immediately.
        """
        update_payload = {
            "assistant_name": "రైతు బంధు",
            "district": "Guntur",
            "selected_language": "te"
        }
        res = self.client.post("/api/settings/profile?user_id=test_farmer_99", json=update_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        self.assertEqual(data["assistant_name"], "రైతు బంధు")
        self.assertEqual(data["district"], "Guntur")
        self.assertEqual(data["selected_language"], "te")

    def test_journey_6_gnani_voice_credit_protection(self):
        """
        Verifies voice API endpoints and strict credit protection.
        Live Gnani calls are disabled by default.
        """
        config_res = self.client.get("/api/voice/config")
        self.assertEqual(config_res.status_code, 200)
        cfg = config_res.json()
        self.assertFalse(cfg["live_enabled"])
        self.assertTrue(cfg["credits_protected"])
        self.assertEqual(cfg["provider"], "browser_native_with_local_tts_fallback")
        
        # Test STT with valid WAV
        wav_bytes = generate_mock_wav(0.3)
        b64 = base64.b64encode(wav_bytes).decode("utf-8")
        with patch.object(sr.Recognizer, "recognize_google", return_value="नमस्ते, मौसम कैसा है?"):
            stt_res = self.client.post("/api/voice/stt", json={"audio_base64": b64, "language": "hi"})
            self.assertEqual(stt_res.status_code, 200)
            stt_data = stt_res.json()
            self.assertFalse(stt_data["is_mock"])
            self.assertGreater(len(stt_data["transcript"]), 0)

    def test_journey_7_multiturn_conversational_slot_filling_api(self):
        """
        Farmer uses the chat API over multiple turns.
        Turn 1: Incomplete market request without commodity or district. Server asks for commodity.
        Turn 2: Farmer supplies commodity. Server asks for district.
        Turn 3: Farmer supplies district. Server returns clearly labelled local illustrative district references.
        Turn 4: Conversation cleared.
        """
        cid = "e2e_multiturn_chat_1"

        # Turn 1: Incomplete request
        t1_res = self.client.post("/api/assistant/chat", json={
            "message": "మార్కెట్ ధరలు చెప్పండి",
            "conversation_id": cid,
            "language": "te",
            "farm_context": {}
        })
        self.assertEqual(t1_res.status_code, 200)
        t1_data = t1_res.json()
        self.assertEqual(t1_data["pending_workflow"], "market_prices")
        self.assertEqual(t1_data["next_slot"], "commodity")
        self.assertIn("సరుకు మార్కెట్ ధర", t1_data["reply_text"])

        # Turn 2: Provide commodity
        t2_res = self.client.post("/api/assistant/chat", json={
            "message": "మిర్చి",
            "conversation_id": cid,
            "language": "te",
            "farm_context": {}
        })
        self.assertEqual(t2_res.status_code, 200)
        t2_data = t2_res.json()
        self.assertEqual(t2_data["pending_workflow"], "market_prices")
        self.assertEqual(t2_data["next_slot"], "district")
        self.assertIn("జిల్లా లేదా సమీప మార్కెట్ యార్డు", t2_data["reply_text"])

        # Turn 3: Provide district
        t3_res = self.client.post("/api/assistant/chat", json={
            "message": "వరంగల్",
            "conversation_id": cid,
            "language": "te",
            "farm_context": {}
        })
        self.assertEqual(t3_res.status_code, 200)
        t3_data = t3_res.json()
        self.assertIsNone(t3_data["pending_workflow"])
        self.assertEqual(t3_data["routed_feature"], "market_prices")
        self.assertIn("ప్రదర్శన డేటా", t3_data["reply_text"])
        self.assertIn("మిర్చి", t3_data["reply_text"])

        # Turn 4: Clear
        clear_res = self.client.post(f"/api/assistant/clear/{cid}")
        self.assertEqual(clear_res.status_code, 200)
        hist_res = self.client.get(f"/api/assistant/history/{cid}")
        self.assertEqual(hist_res.status_code, 200)
        self.assertEqual(len(hist_res.json()), 0)

if __name__ == "__main__":
    unittest.main()
