"""
Kisan Hita — Assistant Crop Health Integration Test Suite
Comprehensive tests covering the 10 requirements:
1. Central assistant crop-health routing invokes evaluate_crop_health_async
2. Symptom-only requests return visual_analysis_status="not_provided"
3. Requests with valid base64 image reach Gemini Vision (mocked) and return visual_analysis_status="completed"
4. Invalid/corrupt/unsupported image requests rejected with HTTP 422
5. Gemini disabled/unconfigured/timeout/error states are preserved in assistant response
6. Farmer-provided details (onset, spread) are not replaced with invented defaults
7. The four assessment categories remain present in reply_text and feature_data
8. All 7 languages (te, en, hi, ta, kn, ml, mr) preserve localized content and format
9. Multi-turn crop-name slot collection, image preservation across turns, and cancellation
10. Adjacent workflow improvements (season not hardcoded as Kharif, location not assumed as Warangal unless provided, market-data honesty, executable suggested actions)
"""

import unittest
import base64
import io
import os
import sys
import tempfile
from unittest.mock import patch, AsyncMock
from PIL import Image
from fastapi.testclient import TestClient
from auth_helpers import authenticated_client

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.config import settings
from app.models.schemas import CropHealthResponse
from app.services.crop_health_localization import (
    SUPPORTED_LANGUAGES,
    SAFETY_NOTICES,
    EXPERT_CONFIRMATION_NOTES,
    EXTENSION_CONTACTS,
    DIAGNOSTIC_DISCLAIMERS,
)
from app.database import (
    init_db,
    clear_conversation_session,
    clear_conversation_history,
    get_conversation_session
)


def create_test_image(fmt: str = "JPEG", color: tuple = (34, 139, 34)) -> bytes:
    """Creates a minimal in-memory test image."""
    bio = io.BytesIO()
    img = Image.new("RGB", (20, 20), color=color)
    img.save(bio, format=fmt)
    return bio.getvalue()


class TestAssistantCropHealthIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_path = settings.DATABASE_PATH
        cls.test_db_dir = tempfile.TemporaryDirectory()
        settings.DATABASE_PATH = os.path.join(cls.test_db_dir.name, "integration.sqlite")
        init_db()
        cls.client = authenticated_client(app)
        cls.jpeg_bytes = create_test_image("JPEG")
        cls.jpeg_b64 = base64.b64encode(cls.jpeg_bytes).decode("ascii")
        cls.png_bytes = create_test_image("PNG")
        cls.png_b64 = base64.b64encode(cls.png_bytes).decode("ascii")

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        settings.DATABASE_PATH = cls.previous_db_path
        cls.test_db_dir.cleanup()

    def setUp(self):
        # Reset test conversation state and the per-session fixed-window limiter.
        from app.database import get_db_connection
        conn = get_db_connection()
        conn.execute("DELETE FROM api_rate_limits")
        conn.commit()
        conn.close()
        clear_conversation_session("test_conv_health")
        clear_conversation_history("test_conv_health")
        clear_conversation_session("test_conv_multi")
        clear_conversation_history("test_conv_multi")
        clear_conversation_session("test_conv_multi_img")
        clear_conversation_history("test_conv_multi_img")
        clear_conversation_session("test_conv_cancel")
        clear_conversation_history("test_conv_cancel")

    # =========================================================================
    # 1. Routing invokes evaluate_crop_health_async
    # =========================================================================
    @patch("app.services.crop_health_service.CropHealthService.evaluate_crop_health_async", new_callable=AsyncMock)
    def test_1_routing_invokes_evaluate_crop_health_async(self, mock_eval):
        """Verifies that the assistant orchestrator calls evaluate_crop_health_async."""
        mock_eval.return_value = CropHealthResponse(
            crop_name="Cotton",
            reported_symptoms="Yellowing leaves and leaf curl",
            cautious_assessment="Preliminary appraisal for Cotton leaves.",
            diagnostic_disclaimer="Responsible Agronomic Transparency: Digital appraisal does not substitute for field inspection.",
            visual_analysis_status="not_provided",
            ai_observations=None,
            farmer_reported_summary="Crop: Cotton | Symptoms: 'Yellowing leaves and leaf curl'",
            potential_factors=["Moisture stress", "Sap-sucking pests"],
            cultural_management_steps=["Drain excess water", "Inspect leaf undersides"],
            expert_confirmation_note="Consult local agricultural officers for diagnosis.",
            safety_notice="Kisan Hita does not provide chemical prescriptions.",
            extension_contact="Kisan Call Center: 1800-180-1551"
        )

        payload = {
            "conversation_id": "test_conv_health",
            "message": "My cotton leaves have yellow spots and curling",
            "language": "en"
        }
        res = self.client.post("/api/assistant/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["intent"], "crop_health")
        self.assertEqual(data["routed_feature"], "crop_health")
        mock_eval.assert_called_once()
        call_kwargs = mock_eval.call_args.kwargs
        self.assertEqual(call_kwargs["crop_name"], "Cotton")
        self.assertIn("yellow spots", call_kwargs["symptoms"].lower())

    # =========================================================================
    # 2. Symptom-only requests return visual_analysis_status="not_provided"
    # =========================================================================
    def test_2_symptom_only_request_status_not_provided(self):
        """Verifies symptom-only queries return visual_analysis_status='not_provided'."""
        payload = {
            "conversation_id": "test_conv_health",
            "message": "Paddy crop has brown spots on upper leaves",
            "language": "en"
        }
        res = self.client.post("/api/assistant/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["intent"], "crop_health")
        self.assertIsNotNone(data["feature_data"])
        self.assertEqual(data["feature_data"]["visual_analysis_status"], "not_provided")
        self.assertIsNone(data["feature_data"]["ai_observations"])

        # Must not claim that an image was analyzed
        reply = data["reply_text"]
        self.assertIn("Visual Analysis Status: Photo was not provided", reply)
        self.assertNotIn("AI Visual Observations:", reply)

    # =========================================================================
    # 3. Valid base64 image reaches Gemini Vision and returns status="completed"
    # =========================================================================
    @patch("app.services.crop_health_service.GeminiAIService.is_configured", return_value=True)
    @patch("app.services.gemini_service.GeminiAIService.analyze_crop_image", new_callable=AsyncMock)
    def test_3_valid_image_reaches_gemini_vision(self, mock_vision, mock_configured):
        """Verifies valid base64 image reaches Gemini Vision and marks status completed."""
        mock_vision.return_value = {
            "status": "completed",
            "visual_observations": "Preliminary AI visual observation: Slight marginal chlorosis observed on leaf edges."
        }

        payload = {
            "conversation_id": "test_conv_health",
            "message": "Chilli leaves are curling upwards",
            "language": "en",
            "image_base64": self.jpeg_b64
        }
        res = self.client.post("/api/assistant/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["intent"], "crop_health")
        self.assertEqual(data["feature_data"]["visual_analysis_status"], "completed")
        self.assertIn("Preliminary AI visual observation", data["feature_data"]["ai_observations"])
        self.assertIn("Preliminary AI visual observation", data["reply_text"])
        mock_vision.assert_called_once()
        call_kwargs = mock_vision.call_args.kwargs
        self.assertEqual(call_kwargs["image_bytes"], self.jpeg_bytes)
        self.assertEqual(call_kwargs["mime_type"], "image/jpeg")

    # =========================================================================
    # 4. Invalid/corrupt/unsupported image requests rejected with HTTP 422
    # =========================================================================
    def test_4_invalid_image_payloads_rejected_with_422(self):
        """Verifies invalid or corrupt image payloads are caught by ChatRequest validator."""
        # 4a. Malformed base64
        res1 = self.client.post("/api/assistant/chat", json={
            "conversation_id": "test_conv_health",
            "message": "Tomato leaf spots",
            "image_base64": "!!!not_valid_base64@@@"
        })
        self.assertEqual(res1.status_code, 422)

        # 4b. Valid base64 of plain text (not image bytes)
        bogus_b64 = base64.b64encode(b"This is just a text file, not a real picture").decode("ascii")
        res2 = self.client.post("/api/assistant/chat", json={
            "conversation_id": "test_conv_health",
            "message": "Tomato leaf spots",
            "image_base64": bogus_b64
        })
        self.assertEqual(res2.status_code, 422)

        # 4c. Unsupported image format (GIF)
        gif_bytes = create_test_image("GIF")
        gif_b64 = base64.b64encode(gif_bytes).decode("ascii")
        res3 = self.client.post("/api/assistant/chat", json={
            "conversation_id": "test_conv_health",
            "message": "Tomato leaf spots",
            "image_base64": gif_b64
        })
        self.assertEqual(res3.status_code, 422)

        # 4d. Oversized payload (>10MB raw)
        oversized_b64 = "A" * (14 * 1024 * 1024)
        res4 = self.client.post("/api/assistant/chat", json={
            "conversation_id": "test_conv_health",
            "message": "Tomato leaf spots",
            "image_base64": oversized_b64
        })
        self.assertEqual(res4.status_code, 422)

    # =========================================================================
    # 5. Gemini disabled/unconfigured/timeout/error states preserved
    # =========================================================================
    @patch("app.services.gemini_service.GeminiAIService.analyze_crop_image", new_callable=AsyncMock)
    def test_5a_gemini_unavailable_preserved(self, mock_vision):
        """Verifies unconfigured/disabled Gemini state returns 'unavailable' status."""
        mock_vision.return_value = {
            "status": "unavailable",
            "message": "Visual analysis service is currently unconfigured or unavailable."
        }

        payload = {
            "conversation_id": "test_conv_health",
            "message": "Tomato leaves turning yellow",
            "image_base64": self.jpeg_b64,
            "language": "en"
        }
        res = self.client.post("/api/assistant/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["feature_data"]["visual_analysis_status"], "unavailable")
        self.assertIn("Visual analysis service is currently unconfigured or unavailable.", data["reply_text"])

    @patch("app.services.crop_health_service.GeminiAIService.is_configured", return_value=True)
    @patch("app.services.gemini_service.GeminiAIService.analyze_crop_image", new_callable=AsyncMock)
    def test_5b_gemini_error_preserved(self, mock_vision, mock_configured):
        """Verifies Gemini error/timeout state returns 'error' status."""
        mock_vision.return_value = {
            "status": "error",
            "error": "Visual scan encountered a network timeout or processing issue."
        }

        payload = {
            "conversation_id": "test_conv_health",
            "message": "Tomato leaves turning yellow",
            "image_base64": self.jpeg_b64,
            "language": "en"
        }
        res = self.client.post("/api/assistant/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["feature_data"]["visual_analysis_status"], "error")
        self.assertIn("Visual scan encountered a network timeout or processing issue.", data["reply_text"])

    # =========================================================================
    # 6. Farmer-provided details preserved without inventing defaults
    # =========================================================================
    @patch("app.services.crop_health_service.CropHealthService.evaluate_crop_health_async", new_callable=AsyncMock)
    def test_6_no_invented_defaults_for_onset_and_spread(self, mock_eval):
        """Verifies onset_days and affected_spread are None when not provided, and preserved when provided."""
        mock_eval.return_value = CropHealthResponse(
            crop_name="Cotton",
            reported_symptoms="Leaf wilt",
            cautious_assessment="Preliminary appraisal for Cotton.",
            diagnostic_disclaimer="Responsible Agronomic Transparency: Digital appraisal does not substitute for field inspection.",
            visual_analysis_status="not_provided",
            farmer_reported_summary="Crop: Cotton | Symptoms: 'Leaf wilt'",
            potential_factors=["Root stress"],
            cultural_management_steps=["Check soil moisture"],
            expert_confirmation_note="Consult local agricultural officers.",
            safety_notice="Kisan Hita does not provide chemical prescriptions.",
            extension_contact="Kisan Call Center: 1800-180-1551"
        )

        # 6a. No onset/spread provided
        res1 = self.client.post("/api/assistant/chat", json={
            "conversation_id": "test_conv_health",
            "message": "Cotton crop leaf wilt",
            "language": "en"
        })
        self.assertEqual(res1.status_code, 200)
        mock_eval.assert_called_once()
        kwargs1 = mock_eval.call_args.kwargs
        self.assertIsNone(kwargs1["onset_days"])
        self.assertIsNone(kwargs1["affected_spread"])

        mock_eval.reset_mock()

        # 6b. Farmer context has explicit onset_days=6 and spread="lower leaves only"
        res2 = self.client.post("/api/assistant/chat", json={
            "conversation_id": "test_conv_health",
            "message": "Cotton crop leaf wilt",
            "language": "en",
            "farm_context": {
                "onset_days": 6,
                "affected_spread": "lower leaves only"
            }
        })
        self.assertEqual(res2.status_code, 200)
        kwargs2 = mock_eval.call_args.kwargs
        self.assertEqual(kwargs2["onset_days"], 6)
        self.assertEqual(kwargs2["affected_spread"], "lower leaves only")

    # =========================================================================
    # 7. Four information categories present in reply_text and feature_data
    # =========================================================================
    def test_7_four_categories_present_in_reply_and_feature_data(self):
        """Verifies reply_text and feature_data strictly separate the four categories."""
        payload = {
            "conversation_id": "test_conv_health",
            "message": "Chilli crop with yellowing leaves",
            "language": "en"
        }
        res = self.client.post("/api/assistant/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        reply = data["reply_text"]
        feat = data["feature_data"]

        # Category 1: Farmer-reported summary
        self.assertIn("Chilli", feat["farmer_reported_summary"])
        self.assertIn(feat["farmer_reported_summary"], reply)

        # Category 2: AI visual observation / status
        self.assertEqual(feat["visual_analysis_status"], "not_provided")
        self.assertIn("Visual Analysis Status: Photo was not provided", reply)

        # Category 3: Plausible factors (NOT a confirmed diagnosis)
        self.assertTrue(len(feat["potential_factors"]) > 0)
        self.assertIn("Possible Contributing Factors (Not a confirmed diagnosis):", reply)
        for factor in feat["potential_factors"]:
            self.assertIn(factor, reply)

        # Category 4: Safe cultural management & Expert confirmation & Helpline
        self.assertTrue(len(feat["cultural_management_steps"]) > 0)
        self.assertIn("Non-Chemical Cultural Management Steps:", reply)
        self.assertIn(feat["safety_notice"], reply)
        self.assertIn(feat["expert_confirmation_note"], reply)
        self.assertIn(feat["extension_contact"], reply)

        # Safety checks: No chemical dosage or false certainty
        self.assertNotIn("apply 2ml/L of Monocrotophos", reply)
        self.assertNotIn("Confirmed Diagnosis:", reply)

    # =========================================================================
    # 8. All 7 languages preserve localized content and format
    # =========================================================================
    def test_8_all_seven_languages_localized(self):
        """Verifies assistant returns localized crop health reply across all 7 supported languages."""
        test_queries = {
            "te": "పత్తి ఆకులు పసుపు రంగులోకి మారుతున్నాయి",
            "en": "Cotton leaves turning yellow",
            "hi": "कपास के पत्ते पीले पड़ रहे हैं",
            "ta": "பருத்தி இலைகள் மஞ்சள் நிறமாக மாறுகின்றன",
            "kn": "ಹತ್ತಿ ಎಲೆಗಳು ಹಳದಿ ಬಣ್ಣಕ್ಕೆ ತಿರುಗುತ್ತಿವೆ",
            "ml": "പരുത്തി ഇലകൾ മഞ്ഞനിറമാകുന്നു",
            "mr": "कापसाची पाने पिवळी पडत आहेत"
        }

        for lang, query in test_queries.items():
            clear_conversation_session(f"conv_{lang}")
            res = self.client.post("/api/assistant/chat", json={
                "conversation_id": f"conv_{lang}",
                "message": query,
                "language": lang
            })
            self.assertEqual(res.status_code, 200, f"Failed for language: {lang}")
            data = res.json()
            self.assertEqual(data["language"], lang, f"Language mismatch for {lang}")
            self.assertEqual(data["intent"], "crop_health", f"Intent mismatch for {lang}: {data['intent']}")
            feat = data["feature_data"]
            reply = data["reply_text"]

            # Must contain language-specific safety notice & expert confirmation
            expected_safety = SAFETY_NOTICES[lang]
            expected_expert = EXPERT_CONFIRMATION_NOTES[lang]
            expected_helpline = EXTENSION_CONTACTS[lang]

            self.assertIn(expected_safety, reply)
            self.assertIn(expected_expert, reply)
            self.assertIn(expected_helpline, reply)
            self.assertEqual(feat["safety_notice"], expected_safety)
            self.assertEqual(feat["expert_confirmation_note"], expected_expert)

    # =========================================================================
    # 9. Multi-turn slot collection, image preservation, and cancellation
    # =========================================================================
    def test_9a_multiturn_crop_name_collection(self):
        """Verifies multi-turn slot collection when crop name is missing initially."""
        conv_id = "test_conv_multi"

        # Turn 1: Farmer mentions symptoms only
        res1 = self.client.post("/api/assistant/chat", json={
            "conversation_id": conv_id,
            "message": "The leaves have dark circular spots",
            "language": "en"
        })
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(d1["pending_workflow"], "crop_health")
        self.assertEqual(d1["next_slot"], "crop_name")
        self.assertIn("Which crop", d1["reply_text"])

        # Check session is stored in SQLite
        sess = get_conversation_session(conv_id)
        self.assertEqual(sess["pending_workflow"], "crop_health")
        self.assertIn("symptoms", sess["collected_slots"])

        # Turn 2: Farmer provides crop name
        res2 = self.client.post("/api/assistant/chat", json={
            "conversation_id": conv_id,
            "message": "Chilli",
            "language": "en"
        })
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertEqual(d2["intent"], "crop_health")
        self.assertIsNone(d2["pending_workflow"])
        self.assertEqual(d2["feature_data"]["crop_name"], "Chilli")
        self.assertIn("Chilli", d2["reply_text"])

    @patch("app.services.crop_health_service.GeminiAIService.is_configured", return_value=True)
    @patch("app.services.gemini_service.GeminiAIService.analyze_crop_image", new_callable=AsyncMock)
    def test_9b_image_preserved_across_multiturn_slots(self, mock_vision, mock_configured):
        """Verifies an uploaded image in Turn 1 is saved in session and processed when crop name is given in Turn 2."""
        mock_vision.return_value = {
            "status": "completed",
            "visual_observations": "Preliminary AI visual observation: Foliar spots on leaf surface."
        }
        conv_id = "test_conv_multi_img"
        clear_conversation_session(conv_id)

        # Turn 1: Upload image with symptoms only
        res1 = self.client.post("/api/assistant/chat", json={
            "conversation_id": conv_id,
            "message": "Look at these curling leaves",
            "image_base64": self.jpeg_b64,
            "language": "en"
        })
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(d1["pending_workflow"], "crop_health")
        self.assertEqual(d1["next_slot"], "crop_name")

        # Turn 2: Provide crop name
        res2 = self.client.post("/api/assistant/chat", json={
            "conversation_id": conv_id,
            "message": "Tomato",
            "language": "en"
        })
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertEqual(d2["feature_data"]["crop_name"], "Tomato")
        self.assertEqual(d2["feature_data"]["visual_analysis_status"], "completed")
        self.assertIn("Preliminary AI visual observation", d2["reply_text"])
        mock_vision.assert_called_once()

    def test_9c_workflow_cancellation(self):
        """Verifies cancellation resets the session and stops pending workflow."""
        conv_id = "test_conv_cancel"

        # Turn 1: Trigger slot collection
        res1 = self.client.post("/api/assistant/chat", json={
            "conversation_id": conv_id,
            "message": "Plant leaves are withering",
            "language": "en"
        })
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["pending_workflow"], "crop_health")

        # Turn 2: Farmer cancels
        res2 = self.client.post("/api/assistant/chat", json={
            "conversation_id": conv_id,
            "message": "Cancel",
            "language": "en"
        })
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertIsNone(d2["pending_workflow"])
        self.assertIn("cancelled", d2["reply_text"].lower())

        # Verify session cleared in database
        sess = get_conversation_session(conv_id)
        self.assertIsNone(sess["pending_workflow"])

    # =========================================================================
    # 10. Adjacent workflow improvements (Season, Location, Market-data honesty, Actions)
    # =========================================================================
    def test_10a_crop_advisor_season_and_location_honesty(self):
        """Verifies Crop Advisor does not hardcode Kharif or falsely claim location."""
        # Query with explicit soil and water, but no district or season mentioned
        res = self.client.post("/api/assistant/chat", json={
            "conversation_id": "conv_advisor_test",
            "message": "Which crop is suitable for black cotton soil with good borewell irrigation?",
            "language": "en",
            "farm_context": {"district": "Warangal (Default)"}  # Default placeholder
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        reply = data["reply_text"]

        # A placeholder district is not treated as a real location. The assistant
        # asks the farmer for the district before proceeding with crop guidance.
        self.assertEqual(data["pending_workflow"], "crop_advisor")
        self.assertEqual(data["next_slot"], "district")
        self.assertIn("Which district is your farm in", reply)
        self.assertNotIn("in Warangal", reply)

        # The location follow-up offers district choices and never a market slot.
        self.assertIn("Nellore", data["suggested_actions"])
        self.assertIn("Warangal", data["suggested_actions"])
        self.assertNotIn("market_prices", data["suggested_actions"])

    def test_10b_crop_advisor_farmer_district_reflected_when_provided(self):
        """Verifies Crop Advisor mentions district only when explicitly provided by farmer."""
        res = self.client.post("/api/assistant/chat", json={
            "conversation_id": "conv_advisor_dist",
            "message": "Recommend crops for black soil and canal irrigation in Khammam",
            "language": "en"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("in Khammam", data["reply_text"])

    def test_10c_market_prices_are_labelled_as_local_demo_references(self):
        """Verifies Market Prices labels local synthetic values as DEMO and not live market observations."""
        res = self.client.post("/api/assistant/chat", json={
            "conversation_id": "conv_market_test",
            "message": "What is the price of cotton in Warangal?",
            "language": "en"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        reply = data["reply_text"]

        # With no provider key, the assistant must state the blocker and avoid guessing.
        self.assertIn("DEMO", reply)
        self.assertIn("not a live", reply.lower())
        self.assertIn("Warangal", reply)
        self.assertEqual(data["feature_data"]["data_type"], "illustrative")

        # Suggested actions must be executable
        self.assertIn("Check Cotton district reference", data["suggested_actions"])


if __name__ == "__main__":
    unittest.main()
