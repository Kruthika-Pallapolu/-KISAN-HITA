import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import init_db, clear_conversation_history
from app.services.intent_router import AssistantOrchestrator
from app.services.gemini_service import GeminiAIService
from app.services.assistant_instructions import build_assistant_instruction
from app.services.market_provider import MarketProviderError
from app.main import app
from fastapi.testclient import TestClient
from app.services.intent_router import detect_intent


class TestAssistantContextQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_explicit_cotton_pest_education_uses_chat_answer_not_diagnostic_template(self):
        self.assertEqual(detect_intent("Tell me about cotton pests."), "general")
        self.assertEqual(detect_intent("There are small white insects under my cotton leaves."), "crop_health")
        cid = "context_exact_cotton_education"
        clear_conversation_history(cid)
        diagnostic_gemini_output = (
            "Farmer-reported details: Cotton pest concern. Onset: not provided. Affected area: not provided. "
            "Visual Analysis Status: no photo. Possible Contributing Factors: generic abiotic stress. "
            "Expert-confirmed diagnosis: consult laboratory. Open CROP HEALTH."
        )
        async def scenario():
            with patch.object(GeminiAIService, "is_configured", return_value=True), patch.object(
                GeminiAIService, "generate_agricultural_response", new=AsyncMock(return_value=diagnostic_gemini_output)
            ) as generated:
                result = await AssistantOrchestrator.process_user_query(
                    "Tell me about cotton pests.", cid, language="en", farm_context={}
                )
            self.assertIn("aphids", result.reply_text.lower())
            self.assertIn("jassids", result.reply_text.lower())
            self.assertIn("whiteflies", result.reply_text.lower())
            self.assertIn("thrips", result.reply_text.lower())
            self.assertIn("bollworms", result.reply_text.lower())
            for rejected in ("Farmer-reported", "Onset:", "Affected area", "Visual Analysis Status", "Possible Contributing Factors", "Expert-confirmed", "Open CROP HEALTH"):
                self.assertNotIn(rejected.lower(), result.reply_text.lower())
            self.assertEqual(result.routed_feature, "ask_kisan")
            self.assertIsNone(result.feature_data)
            self.assertIn("white insects under leaves", result.reply_text.lower())
            self.assertTrue(generated.await_args.kwargs["query"].find("not a field diagnosis") >= 0)
        asyncio.run(scenario())

    def test_actual_chat_endpoint_returns_education_text_for_frontend_to_render(self):
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/auth/guest").status_code, 200)
            with patch.object(GeminiAIService, "is_configured", return_value=True), patch.object(
                GeminiAIService, "generate_agricultural_response", new=AsyncMock(return_value="Farmer-reported details: Onset: not provided. Possible Contributing Factors: abiotic stress. Open CROP HEALTH.")
            ):
                response = client.post("/api/assistant/chat", json={
                    "message":"Tell me about cotton pests.", "language":"en", "farm_context":{},
                })
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertIn("aphids", body["reply_text"].lower())
            self.assertEqual(body["routed_feature"], "ask_kisan")
            self.assertIsNone(body["feature_data"])

    def test_actual_field_symptom_still_uses_crop_health_assessment(self):
        cid = "context_actual_diagnosis"
        clear_conversation_history(cid)
        async def scenario():
            with patch.object(GeminiAIService, "is_configured", return_value=False):
                result = await AssistantOrchestrator.process_user_query(
                    "My cotton leaves are curling and have yellow spots.", cid, language="en", farm_context={}
                )
            self.assertEqual(result.routed_feature, "crop_health")
            self.assertIsNotNone(result.feature_data)
            self.assertEqual(result.feature_data["crop_name"], "Cotton")
            self.assertFalse(result.feature_data["has_image"])
            self.assertEqual(result.feature_data["visual_analysis_status"], "not_provided")
            self.assertIn("possible contributing factors", result.reply_text.lower())
        asyncio.run(scenario())

    def test_cotton_pest_question_uses_crop_context_without_claiming_a_photo(self):
        cid = "context_pests_cotton"
        clear_conversation_history(cid)
        async def scenario():
            first = await AssistantOrchestrator.process_user_query("What insects affect my field?", cid, language="en", farm_context={})
            self.assertEqual(first.next_slot, "crop_name")
            with patch.object(GeminiAIService, "is_configured", return_value=True), patch.object(
                GeminiAIService, "generate_agricultural_response", new=AsyncMock(return_value="Cotton may be affected by aphids, jassids, whiteflies, thrips and bollworms. Check leaf undersides and look for damaged squares or boll holes. What signs are you seeing?")
            ) as generated:
                second = await AssistantOrchestrator.process_user_query("Cotton", cid, language="en", farm_context={})
            self.assertTrue(generated.await_args.kwargs["query"].find("Cotton") >= 0)
            self.assertIn("bollworms", second.reply_text)
            self.assertEqual(second.feature_data["has_image"], False)
            self.assertEqual(second.feature_data["visual_analysis_status"], "not_provided")
            self.assertIsNone(second.feature_data["ai_observations"])
            self.assertEqual(second.pending_workflow, None)
        asyncio.run(scenario())

    def test_white_insects_are_reported_as_uncertain_text_not_visual_identification(self):
        cid = "context_white_insects"
        clear_conversation_history(cid)
        async def scenario():
            with patch.object(GeminiAIService, "is_configured", return_value=True), patch.object(
                GeminiAIService, "generate_agricultural_response", new=AsyncMock(return_value="Farmer-reported details: Cotton leaves. Onset: not provided. Affected area: not provided. Visual Analysis Status: no photo. Possible Contributing Factors: generic abiotic stress. Expert-confirmed diagnosis: consult a lab.")
            ):
                result = await AssistantOrchestrator.process_user_query("Cotton has white insects under the leaves", cid, language="en", farm_context={})
            self.assertEqual(result.feature_data["has_image"], False)
            self.assertEqual(result.feature_data["visual_analysis_status"], "not_provided")
            self.assertNotIn("visually identified", result.reply_text.lower())
            self.assertIn("possibility", result.reply_text.lower())
            self.assertIn("whiteflies", result.reply_text.lower())
            self.assertNotIn("affected area", result.reply_text.lower())
            self.assertNotIn("generic abiotic stress", result.reply_text.lower())
        asyncio.run(scenario())

    def test_cotton_pest_question_has_supported_local_fallback_when_gemini_is_unavailable(self):
        cid = "context_pests_cotton_fallback"
        clear_conversation_history(cid)
        async def scenario():
            with patch.object(GeminiAIService, "is_configured", return_value=False):
                first = await AssistantOrchestrator.process_user_query("What insects affect my field?", cid, language="en", farm_context={})
                result = await AssistantOrchestrator.process_user_query("Cotton", cid, language="en", farm_context={})
            self.assertIn("whiteflies", result.reply_text.lower())
            self.assertIn("bollworms", result.reply_text.lower())
            self.assertIn("not a finding", result.reply_text.lower())
            self.assertFalse(result.feature_data["has_image"])
            self.assertEqual(result.feature_data["visual_analysis_status"], "not_provided")
        asyncio.run(scenario())

    def test_central_instruction_covers_context_language_and_factual_boundaries(self):
        prompt = build_assistant_instruction("te", {"district":"Nellore", "soil_type":"Black Cotton Soil", "season":"Kharif"})
        for phrase in ["Telugu", "Nellore", "Black Cotton Soil", "Kharif", "Never claim to have seen", "Never invent a local forecast", "at most one"]:
            self.assertIn(phrase, prompt)

    def test_market_provider_failure_never_reaches_gemini_or_guesses_a_price(self):
        cid = "context_market_no_guess"
        clear_conversation_history(cid)
        async def scenario():
            first = await AssistantOrchestrator.process_user_query("Check Chilli mandi prices", cid, language="en", farm_context={})
            self.assertEqual(first.next_slot, "district")
            with patch("app.services.market_service.MarketPriceService.get_market_prices", new=AsyncMock(side_effect=MarketProviderError("provider_not_configured", "not configured"))), patch.object(
                GeminiAIService, "generate_agricultural_response", new_callable=AsyncMock
            ) as generated:
                response = await AssistantOrchestrator.process_user_query("Nellore", cid, language="en", farm_context={})
            self.assertIn("will not invent or substitute", response.reply_text)
            self.assertIn("Nellore", response.reply_text)
            generated.assert_not_awaited()
        asyncio.run(scenario())
