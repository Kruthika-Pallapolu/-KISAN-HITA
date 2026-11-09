import unittest
import asyncio
import os
import sys
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from auth_helpers import authenticated_client

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.config import settings
from app.services.gemini_service import GeminiAIService
from app.database import init_db, get_conversation_history, clear_conversation_history
from app.services.intent_router import AssistantOrchestrator, response_matches_language_script

class TestGeminiAndAIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = authenticated_client(app)

    def test_gemini_status_schema_and_credential_protection(self):
        """Verifies Gemini status reporting schema and guarantees API keys are NEVER exposed (not even masked)."""
        status = GeminiAIService.get_connection_status()
        self.assertIn("status", status)
        self.assertIn("provider", status)
        self.assertIn("sdk_available", status)
        self.assertIn("key_configured", status)
        self.assertNotIn("masked_key", status)
        self.assertNotIn("api_key", status)
        self.assertIn("model", status)
        self.assertEqual(status["provider"], "Google GenAI (Gemini)")

    def test_gemini_test_connection_when_unconfigured(self):
        """Verifies test_connection returns not_configured when no key is set."""
        orig_key = settings.GEMINI_API_KEY
        try:
            settings.GEMINI_API_KEY = ""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(GeminiAIService.test_connection())
            loop.close()
            
            self.assertEqual(res["status"], "not_configured")
            self.assertIn("not configured", res["message"].lower())
            self.assertEqual(res["latency_ms"], 0)
        finally:
            settings.GEMINI_API_KEY = orig_key

    def test_settings_ai_endpoints(self):
        """Verifies /api/settings/ai-config and /api/settings/test-ai endpoints."""
        # 1. GET ai-config - verifies status and no credential leakage
        get_res = self.client.get("/api/settings/ai-config")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertEqual(data["provider"], "Google GenAI (Gemini)")
        self.assertNotIn("api_key", data)
        self.assertNotIn("masked_key", data)
        
        # 2. POST ai-config update is strictly 403 Forbidden (no dynamic public key mutation)
        upd_res = self.client.post("/api/settings/ai-config", json={
            "model": "gemini-2.5-flash",
            "enabled": True
        })
        self.assertEqual(upd_res.status_code, 403)
        self.assertIn("disabled", upd_res.json()["detail"].lower())

    def test_multi_turn_conversational_context(self):
        """Verifies conversation history is retained and accessible across turns."""
        conv_id = "test_multi_turn_conv_42"
        clear_conversation_history(conv_id)
        
        # Turn 1
        res1 = self.client.post("/api/assistant/chat", json={
            "message": "Which crop is best for black soil?",
            "conversation_id": conv_id,
            "language": "en",
            "farm_context": {"district": "Warangal", "soil_type": "Black Cotton Soil"}
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["intent"], "crop_advisor")
        
        # Verify history in DB has 2 messages (user + assistant)
        history = get_conversation_history(conv_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["sender"], "user")
        self.assertEqual(history[1]["sender"], "assistant")
        
        # Turn 2: Follow-up question
        res2 = self.client.post("/api/assistant/chat", json={
            "message": "How much irrigation water does it need?",
            "conversation_id": conv_id,
            "language": "en",
            "farm_context": {"district": "Warangal", "soil_type": "Black Cotton Soil"}
        })
        self.assertEqual(res2.status_code, 200)
        
        # Verify history grew to 4 messages
        history2 = get_conversation_history(conv_id)
        self.assertEqual(len(history2), 4)

    def test_crop_health_with_image(self):
        """Verifies crop health diagnosis handles image_base64 and returns ai_observations schema."""
        sample_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "Yellow leaves with brown margins",
            "onset_days": "2-3 days ago",
            "affected_spread": "Few scattered plants",
            "image_base64": sample_img,
            "language": "en"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["has_image"])
        self.assertIn("ai_observations", data)

    def test_language_script_validation_covers_all_supported_locales(self):
        localized = {
            "en": "This is an English response.",
            "te": "ఇది తెలుగు సమాధానం.",
            "hi": "यह हिंदी में उत्तर है।",
            "ta": "இது தமிழ் பதில்.",
            "kn": "ಇದು ಕನ್ನಡ ಉತ್ತರ.",
            "ml": "ഇത് മലയാളം മറുപടിയാണ്.",
            "mr": "हे मराठी उत्तर आहे.",
        }
        for language, text in localized.items():
            with self.subTest(language=language):
                self.assertTrue(response_matches_language_script(text, language))
                self.assertFalse(response_matches_language_script(localized["en"], language) if language != "en" else response_matches_language_script(localized["te"], language))

    def test_english_gemini_reply_is_not_returned_for_telugu_request(self):
        conv_id = "test_gemini_wrong_language_te"
        clear_conversation_history(conv_id)

        async def run_request():
            with patch.object(
                GeminiAIService,
                "generate_agricultural_response",
                new=AsyncMock(return_value="Crop rotation improves soil health and reduces risk."),
            ):
                return await AssistantOrchestrator.process_user_query(
                    "పంటల వైవిధ్యం వల్ల ఏమి ప్రయోజనం?",
                    conv_id,
                    language="te",
                    farm_context={},
                    conversation_history=[],
                )

        response = asyncio.run(run_request())
        self.assertEqual(response.language, "te")
        self.assertIn("క్షమించండి", response.reply_text)
        self.assertNotIn("Crop rotation", response.reply_text)
        self.assertTrue(response_matches_language_script(response.reply_text, "te"))
        clear_conversation_history(conv_id)

if __name__ == "__main__":
    unittest.main()

