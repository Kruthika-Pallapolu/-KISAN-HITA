import unittest
import asyncio
import json
import os
import sys
import time
from unittest.mock import patch, AsyncMock
import speech_recognition as sr

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import init_db, get_user_profile, update_user_profile, save_conversation_message, get_conversation_history, clear_conversation_history
from app.services.intent_router import detect_intent, AssistantOrchestrator
from app.services.weather_service import WeatherService, WeatherProviderUnavailable
from app.services.crop_service import CropAdvisorService
from app.services.crop_health_service import CropHealthService
from app.services.market_service import MarketPriceService
from app.services.gnani_voice import get_voice_provider, MockGnaniProvider, generate_mock_wav
from app.config import settings

class MockHttpxResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

async def mock_weather_http_get(_client, url, params=None):
    params = params or {}
    if url.endswith("/search.json"):
        district, _, rest = params.get("q", "").partition(",")
        state = rest.split(",")[0].strip()
        return MockHttpxResponse(200, [{"name": district.strip(), "region": state, "country": "India", "lat": 17.96, "lon": 79.59, "id": 1}])
    payload = json.loads(json.dumps(WEATHERAPI_MOCK_DATA))
    if params.get("q"):
        lat, lon = params["q"].split(",")
        payload["location"].update({"lat": float(lat), "lon": float(lon)})
    return MockHttpxResponse(200, payload)

WEATHERAPI_MOCK_DATA = {
    "location": {"name": "Warangal", "region": "Telangana", "country": "India", "lat": 17.96, "lon": 79.59},
    "current": {"temp_c": 29.5, "feelslike_c": 31.0, "humidity": 65, "wind_kph": 12.0,
                "wind_dir": "SW", "vis_km": 10.0, "precip_mm": 0.0,
                "condition": {"text": "Partly cloudy", "code": 1003, "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png"}},
    "forecast": {"forecastday": [
        {"date": "2026-11-09", "day": {"maxtemp_c": 31.0, "mintemp_c": 22.0, "daily_chance_of_rain": 15, "condition": {"text": "Partly cloudy", "code": 1003, "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png"}}},
        {"date": "2026-11-10", "day": {"maxtemp_c": 32.0, "mintemp_c": 21.5, "daily_chance_of_rain": 20, "condition": {"text": "Cloudy", "code": 1006, "icon": "//cdn.weatherapi.com/weather/64x64/day/119.png"}}},
        {"date": "2026-11-11", "day": {"maxtemp_c": 31.5, "mintemp_c": 22.0, "daily_chance_of_rain": 25, "condition": {"text": "Rain", "code": 1183, "icon": "//cdn.weatherapi.com/weather/64x64/day/296.png"}}},
    ]},
}

class TestKisanHitaBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings.WEATHERAPI_KEY = "offline-test-key"
        init_db()

    def test_database_profile_and_conversation(self):
        uid = f"user_{int(time.monotonic()*1000)}"
        # Test profile get & update (unverified default district was removed for data integrity)
        p = get_user_profile(uid)
        self.assertIsNotNone(p)
        self.assertIsNone(p["district"])
        
        updated = update_user_profile(uid, {"district": "Nellore", "selected_language": "te"})
        self.assertEqual(updated["district"], "Nellore")
        self.assertEqual(updated["selected_language"], "te")
        
        # Test message persistence
        cid = "test_conv_123"
        mid = save_conversation_message(cid, "user", "Will it rain tomorrow?", language="en")
        self.assertTrue(mid.startswith("msg_"))
        
        hist = get_conversation_history(cid)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["text"], "Will it rain tomorrow?")
        
        # Test clear history
        clear_conversation_history(cid)
        self.assertEqual(len(get_conversation_history(cid)), 0)

    def test_intent_detection_multilingual(self):
        # Weather
        self.assertEqual(detect_intent("Will it rain tomorrow in Warangal?"), "weather")
        self.assertEqual(detect_intent("రేపు వర్షం పడుతుందా?"), "weather")
        self.assertEqual(detect_intent("क्या कल बारिश होगी?"), "weather")
        self.assertEqual(detect_intent("நாளை மழை பெய்யுமா?"), "weather")
        
        # Crop Advisor
        self.assertEqual(detect_intent("Which crop can I grow in black soil?"), "crop_advisor")
        self.assertEqual(detect_intent("Help me choose a crop"), "crop_advisor")
        self.assertEqual(detect_intent("నల్ల రేగడి నేలలో ఏ పంట వేయాలి?"), "crop_advisor")
        self.assertEqual(detect_intent("काली मिट्टी में कौन सी फसल उगाएं?"), "crop_advisor")
        
        # Crop Health
        self.assertEqual(detect_intent("My cotton leaves are turning yellow with spots"), "crop_health")
        self.assertEqual(detect_intent("పత్తి ఆకులు పసుపు రంగులోకి మారుతున్నాయి"), "crop_health")
        self.assertEqual(detect_intent("कपास की पत्तियां पीली हो रही हैं"), "crop_health")
        
        # Market Prices
        self.assertEqual(detect_intent("What is the current chilli price in Guntur mandi?"), "market_prices")
        self.assertEqual(detect_intent("గుంటూరు మార్కెట్లో మిర్చి ధర ఎంత?"), "market_prices")
        self.assertEqual(detect_intent("गुंटूर मंडी में मिर्च का भाव क्या है?"), "market_prices")
        
        # General
        self.assertEqual(detect_intent("Namaste Kisan Assistant"), "general")

    def test_weather_service_and_advisory(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with patch("httpx.AsyncClient.get", new=mock_weather_http_get):
            data = loop.run_until_complete(WeatherService.get_district_weather("Warangal", "Telangana", "en"))
        loop.close()
        
        self.assertEqual(data.district, "Warangal")
        self.assertGreater(data.temperature, -10)
        self.assertLess(data.temperature, 55)
        self.assertIsNotNone(data.irrigation_advice)
        self.assertIsNotNone(data.spray_suitability)
        self.assertIsNotNone(data.produce_protection)
        self.assertFalse(data.is_official_alert)
        self.assertGreaterEqual(len(data.forecast), 3)

    def test_weather_service_fails_closed_when_current_measurements_are_missing(self):
        # Isolate the provider-response assertion from a cached forecast in
        # another test that uses the same district and coordinates.
        WeatherService._forecast_cache.clear()
        incomplete = {
            "location": WEATHERAPI_MOCK_DATA["location"],
            "current": {key: value for key, value in WEATHERAPI_MOCK_DATA["current"].items() if key != "temp_c"},
            "forecast": WEATHERAPI_MOCK_DATA["forecast"],
        }
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def incomplete_get(_client, url, params=None):
            if url.endswith("/search.json"):
                return await mock_weather_http_get(_client, url, params)
            return MockHttpxResponse(200, incomplete)
        with patch("httpx.AsyncClient.get", new=incomplete_get):
            with self.assertRaises(WeatherProviderUnavailable):
                loop.run_until_complete(WeatherService.get_district_weather("Warangal", "Telangana", "en"))
        loop.close()

    def test_weather_service_fails_closed_when_rain_probability_is_missing(self):
        WeatherService._forecast_cache.clear()
        incomplete = {
            "location": WEATHERAPI_MOCK_DATA["location"],
            "current": WEATHERAPI_MOCK_DATA["current"],
            "forecast": {"forecastday": []},
        }
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def incomplete_get(_client, url, params=None):
            if url.endswith("/search.json"):
                return await mock_weather_http_get(_client, url, params)
            return MockHttpxResponse(200, incomplete)
        with patch("httpx.AsyncClient.get", new=incomplete_get):
            with self.assertRaises(WeatherProviderUnavailable):
                loop.run_until_complete(WeatherService.get_district_weather("Warangal", "Telangana", "en"))
        loop.close()

    def test_crop_advisor_evidence_and_constraints(self):
        res = CropAdvisorService.get_recommendations("Black Cotton Soil", "Good irrigation", "Kharif (Monsoon)", "Warangal", "Telangana")
        
        # Demo reference suggestions remain available with an explicit caveat.
        self.assertGreater(len(res.recommendations), 0)
        self.assertEqual(res.total_found, len(res.recommendations))
        self.assertIn("demo", res.disclaimer.lower())
        self.assertIn("not scientifically verified", res.disclaimer.lower())
        self.assertIn("kvk", res.disclaimer.lower())

        # Candidate records remain stored separately from verified advice.
        from backend.app.services.crop_service import UNVERIFIED_CROP_REFERENCE_DATA
        self.assertGreater(len(UNVERIFIED_CROP_REFERENCE_DATA), 0)

    def test_crop_health_safety_and_honesty(self):
        res = CropHealthService.evaluate_crop_health(
            crop_name="Cotton",
            symptoms="Lower leaves turning yellow with brown spots",
            onset_days="3 days ago",
            affected_spread="Scattered plants",
            language="en"
        )
        self.assertEqual(res.crop_name, "Cotton")
        self.assertGreater(len(res.potential_factors), 0)
        self.assertGreater(len(res.cultural_management_steps), 0)
        # Verify strict safety notice present
        self.assertIn("Safety Notice", res.safety_notice)
        self.assertIn("Never apply unverified synthetic chemical pesticides", res.safety_notice)
        self.assertIn("Krishi Vigyan Kendra", res.extension_contact)

    def test_market_prices_integrity(self):
        res = asyncio.run(MarketPriceService.get_market_prices(commodity="Chilli", district="Guntur", state="Andhra Pradesh"))
        self.assertGreater(len(res.records), 0)
        self.assertEqual(res.total_count, len(res.records))
        self.assertFalse(res.is_live_api)
        self.assertEqual(res.data_type, "illustrative")
        self.assertIn("DEMO DATA", res.disclaimer)
        self.assertEqual(res.records[0].unit, "kg")
        self.assertIsNone(res.records[0].market)


    def test_market_prices_respect_requested_location(self):
        nellore = asyncio.run(MarketPriceService.get_market_prices(commodity="Chilli", district="Nellore"))
        self.assertTrue(nellore.records)
        self.assertEqual({r.state for r in nellore.records}, {"Andhra Pradesh"})
        self.assertEqual({r.district for r in nellore.records}, {"Nellore"})
        self.assertIn("No other district or state was substituted", nellore.disclaimer)

        guntur = asyncio.run(MarketPriceService.get_market_prices(commodity="Chilli", district="Guntur"))
        self.assertTrue(guntur.records)
        self.assertEqual({r.district for r in guntur.records}, {"Guntur"})
        self.assertEqual({r.state for r in guntur.records}, {"Andhra Pradesh"})

        unavailable = asyncio.run(MarketPriceService.get_market_prices(commodity="Chilli", district="Nowhere"))
        self.assertEqual(unavailable.records, [])
        self.assertIn("Nowhere", unavailable.disclaimer)


    def test_gnani_voice_protection(self):
        # Strict requirement: live Gnani is disabled by default to protect ~5000 credits
        self.assertFalse(settings.GNANI_LIVE_ENABLED)
        provider = get_voice_provider()
        self.assertIsInstance(provider, MockGnaniProvider)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sample_audio = generate_mock_wav(0.2)
        with patch.object(sr.Recognizer, "recognize_google", return_value="హలో"):
            stt_res = loop.run_until_complete(provider.speech_to_text(sample_audio, "te"))
        tts_res = loop.run_until_complete(provider.text_to_speech("హలో", "te"))
        loop.close()
        
        self.assertFalse(stt_res.is_mock)
        self.assertFalse(tts_res.is_mock)
        self.assertGreater(len(stt_res.transcript), 0)
        self.assertEqual(provider.get_provider_info()["type"], "temporary_development")

    def test_assistant_orchestrator_execution(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        with patch("httpx.AsyncClient.get", new=mock_weather_http_get):
            
            # Test weather query
            resp_w = loop.run_until_complete(AssistantOrchestrator.process_user_query(
                "Will it rain tomorrow?", "c1", language="en", farm_context={"district": "Warangal"}
            ))
            self.assertEqual(resp_w.routed_feature, "weather")
            self.assertIsNotNone(resp_w.feature_data)
            self.assertIn("Warangal", resp_w.reply_text)
            self.assertFalse(resp_w.audio_available, "chat responses must not claim audio that was not generated")
            
            # Test Telugu query
            resp_te = loop.run_until_complete(AssistantOrchestrator.process_user_query(
                "రేపు వర్షం పడుతుందా?", "c2", language="te", farm_context={"district": "Nellore"}
            ))
            self.assertEqual(resp_te.routed_feature, "weather")
            self.assertEqual(resp_te.language, "te")
            self.assertIn("Nellore", resp_te.reply_text)
            self.assertFalse(resp_te.audio_available)
            
        loop.close()

    def test_assistant_does_not_answer_unhandled_questions_with_a_generic_greeting(self):
        unavailable_replies = {
            "te": "నమ్మదగిన సమాధానం",
            "en": "couldn't generate a reliable answer",
            "hi": "भरोसेमंद जवाब",
            "ta": "நம்பகமான பதிலை",
            "kn": "ವಿಶ್ವಾಸಾರ್ಹ ಉತ್ತರ",
            "ml": "വിശ്വസനീയമായ മറുപടി",
            "mr": "विश्वासार्ह उत्तर",
        }
        with patch(
            "app.services.intent_router.GeminiAIService.generate_agricultural_response",
            new_callable=AsyncMock,
            return_value=None,
        ):
            for index, (language, expected) in enumerate(unavailable_replies.items()):
                response = asyncio.run(AssistantOrchestrator.process_user_query(
                    "How can I check if my soil needs watering?",
                    f"fallback_honesty_{index}",
                    language=language,
                ))
                self.assertIn(expected, response.reply_text)
                self.assertNotIn("Namaste! I am your Kisan Assistant", response.reply_text)

    def test_crop_advisor_chat_reply_is_farmer_friendly_in_all_supported_languages(self):
        expected_localized_caveats = {
            "te": "ధృవీకరించిన సిఫార్సులు కావు",
            "en": "not verified for your field",
            "hi": "सत्यापित सिफारिशें नहीं हैं",
            "ta": "சரிபார்க்கப்பட்ட பரிந்துரைகள் அல்ல",
            "kn": "ಪರಿಶೀಲಿತ ಶಿಫಾರಸುಗಳಲ್ಲ",
            "ml": "സ്ഥിരീകരിച്ച ശുപാർശകളല്ല",
            "mr": "पडताळलेल्या शिफारसी नाहीत",
        }
        for index, (language, caveat) in enumerate(expected_localized_caveats.items()):
            response = asyncio.run(AssistantOrchestrator.process_user_query(
                "Which crops may suit black cotton soil in Nellore with rainfed conditions during Rabi?",
                f"natural_crop_reply_{index}",
                language=language,
                farm_context={
                    "district": "Nellore", "state": "Andhra Pradesh", "soil_type": "Black Cotton Soil",
                    "water_source": "Rain-dependent", "growing_season": "Rabi (Winter)",
                },
            ))
            self.assertEqual(response.routed_feature, "crop_advisor")
            self.assertIn(caveat, response.reply_text)
            self.assertNotIn("DEMO", response.reply_text.upper())
            self.assertIn("KVK", response.reply_text)

if __name__ == "__main__":
    unittest.main()
