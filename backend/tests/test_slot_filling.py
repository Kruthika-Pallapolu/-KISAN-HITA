import unittest
import asyncio
import os
import sys
import json
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import init_db, clear_conversation_history, get_conversation_session
from app.services.intent_router import AssistantOrchestrator, extract_mandi
from app.models.schemas import ForecastDay, WeatherData
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
        lat, lon = (15.5, 78.5) if district.strip() == "Khammam" else (17.96, 79.59)
        return MockHttpxResponse(200, [{"name": district.strip(), "region": state, "country": "India", "lat": lat, "lon": lon, "id": 1}])
    payload = json.loads(json.dumps(WEATHERAPI_MOCK_DATA))
    query = params.get("q", "")
    lat, lon = query.split(",")
    if float(lat) < 16:
        payload["location"].update({"name": "Khammam", "region": "Telangana", "lat": float(lat), "lon": float(lon)})
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

class TestSequentialSlotFilling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings.WEATHERAPI_KEY = "offline-test-key"
        init_db()

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_named_market_parser_requires_explicit_yard_and_ignores_price_phrase(self):
        self.assertIsNone(extract_mandi("Check current Chilli Mandi prices"))
        self.assertEqual(extract_mandi("search chilli at enumamula apmc yard"), "enumamula apmc yard")

    def test_market_price_sequential_slot_filling(self):
        conv_id = "test_slot_market_1"
        clear_conversation_history(conv_id)

        # Turn 1: Generic query without commodity or district
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Show me today's market prices",
            conv_id,
            language="en",
            farm_context={}
        ))
        self.assertEqual(r1.pending_workflow, "market_prices")
        self.assertEqual(r1.next_slot, "commodity")
        self.assertIn("Which crop or commodity", r1.reply_text)

        # Verify session saved in DB
        sess = get_conversation_session(conv_id)
        self.assertEqual(sess["pending_workflow"], "market_prices")
        self.assertEqual(sess["missing_slots"], ["commodity", "district"])

        # Turn 2: Farmer provides commodity "Chilli"
        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Chilli",
            conv_id,
            language="en",
            farm_context={}
        ))
        self.assertEqual(r2.pending_workflow, "market_prices")
        self.assertEqual(r2.next_slot, "district")
        self.assertIn("Which district or mandi", r2.reply_text)

        # Turn 3: Farmer provides district "Warangal"
        r3 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Warangal",
            conv_id,
            language="en",
            farm_context={}
        ))
        self.assertIsNone(r3.pending_workflow)
        self.assertEqual(r3.routed_feature, "market_prices")
        self.assertIsNotNone(r3.feature_data)
        self.assertIn("Chilli", r3.reply_text)
        self.assertIn("DEMO", r3.reply_text)
        self.assertIn("illustrative", r3.reply_text.lower())
        self.assertIn("DEMO", r3.reply_text)
        self.assertIn("Warangal", r3.reply_text)

        # Verify session cleared in DB
        sess_cleared = get_conversation_session(conv_id)
        self.assertIsNone(sess_cleared["pending_workflow"])

    def test_chilli_nellore_flow_does_not_substitute_guntur(self):
        conv_id = "test_slot_chilli_nellore_no_substitution"
        clear_conversation_history(conv_id)
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Check chilli price", conv_id, language="en", farm_context={}
        ))
        self.assertEqual(r1.next_slot, "district")

        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Nellore", conv_id, language="en", farm_context={}
        ))
        self.assertEqual(r2.routed_feature, "market_prices")
        self.assertEqual(r2.feature_data["data_type"], "illustrative")
        self.assertIn("illustrative", r2.reply_text.lower())
        self.assertIn("Nellore", r2.reply_text)
        self.assertIn("not a live", r2.reply_text.lower())
        self.assertNotIn("Guntur", r2.reply_text)

    def test_explicit_chilli_market_query_does_not_ask_for_commodity_again(self):
        conv_id = "test_slot_explicit_chilli_then_nellore"
        clear_conversation_history(conv_id)
        # A stale commodity prompt can remain after a browser reload. The new
        # complete query must fill Chilli and proceed directly to the location.
        from app.database import save_conversation_session
        save_conversation_session(conv_id, "market_prices", {}, ["commodity"])

        first = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Check the current Chilli Mandi prices", conv_id, language="en", farm_context={}
        ))
        self.assertEqual(first.next_slot, "district")
        self.assertEqual(first.collected_slots["commodity"], "Chilli")
        self.assertIn("Which district or mandi", first.reply_text)
        self.assertNotIn("Which crop or commodity", first.reply_text)

        result = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Nellore", conv_id, language="en", farm_context={}
        ))
        self.assertEqual(result.feature_data["data_type"], "illustrative")
        self.assertIn("illustrative", result.reply_text.lower())
        self.assertNotIn("live price", result.reply_text.lower())
        self.assertNotIn("Guntur", result.reply_text)

    def test_chilli_explicit_mandi_slot_is_exact(self):
        conv_id = "test_slot_chilli_explicit_mandi"
        clear_conversation_history(conv_id)
        self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "What are the market prices?", conv_id, language="en", farm_context={}
        ))
        self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Chilli", conv_id, language="en", farm_context={}
        ))
        result = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Enumamula APMC Yard", conv_id, language="en", farm_context={}
        ))
        self.assertEqual(result.feature_data["total_count"], 0)
        self.assertEqual(result.feature_data["data_type"], "illustrative")
        self.assertIn("No local illustrative Chilli reference", result.reply_text)
        self.assertNotIn("Enumamula APMC Yard, Warangal", result.reply_text)

    def test_telugu_crop_advisor_sequential_slot_filling(self):
        conv_id = "test_slot_crop_te_1"
        clear_conversation_history(conv_id)

        # Turn 1: Farmer asks in Telugu "ఏ పంట వేయాలి?" (Which crop to grow?)
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "ఈ కాలంలో ఏ పంట వేయాలి?",
            conv_id,
            language="te",
            farm_context={"district": "Warangal"}
        ))
        self.assertEqual(r1.pending_workflow, "crop_advisor")
        self.assertEqual(r1.next_slot, "soil_type")
        self.assertIn("నేల రకం ఏమిటి", r1.reply_text)

        # Turn 2: Farmer says "నల్ల రేగడి నేల" (Black cotton soil)
        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "నల్ల రేగడి నేల",
            conv_id,
            language="te",
            farm_context={"district": "Warangal"}
        ))
        self.assertEqual(r2.pending_workflow, "crop_advisor")
        self.assertEqual(r2.next_slot, "water_source")
        self.assertIn("నీటి సదుపాయం ఎలా ఉంది", r2.reply_text)

        # Turn 3: Farmer says "మంచి నీరు ఉంది" (Have good irrigation)
        r3 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "మంచి నీరు ఉంది",
            conv_id,
            language="te",
            farm_context={"district": "Warangal"}
        ))
        self.assertIsNone(r3.pending_workflow)
        self.assertEqual(r3.routed_feature, "crop_advisor")
        self.assertIsNotNone(r3.feature_data)
        self.assertNotIn("DEMO", r3.reply_text.upper())
        self.assertIn("ధృవీకరించిన సిఫార్సులు కావు", r3.reply_text)
        self.assertIn("స్థానిక KVK", r3.reply_text)

    def test_crop_choice_clears_stale_market_flow_and_keeps_district_in_crop_advisor(self):
        conv_id = "test_crop_choice_after_stale_market"
        clear_conversation_history(conv_id)
        from app.database import save_conversation_session
        save_conversation_session(conv_id, "market_prices", {}, ["district"])

        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Help me choose a crop", conv_id, language="en", farm_context={"growing_season": "Rabi (Winter)"}
        ))
        self.assertEqual(r1.routed_feature, "crop_advisor")
        self.assertEqual(r1.pending_workflow, "crop_advisor")
        self.assertEqual(r1.next_slot, "district")
        self.assertIn("Which district is your farm in", r1.reply_text)
        self.assertNotIn("mandi", r1.reply_text.lower())

        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Nellore", conv_id, language="en", farm_context={"growing_season": "Rabi (Winter)"}
        ))
        self.assertEqual(r2.routed_feature, "crop_advisor")
        self.assertEqual(r2.next_slot, "soil_type")
        self.assertEqual(r2.collected_slots["district"], "Nellore")

        r3 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Black soil", conv_id, language="en", farm_context={"growing_season": "Rabi (Winter)"}
        ))
        self.assertEqual(r3.routed_feature, "crop_advisor")
        self.assertEqual(r3.next_slot, "water_source")
        self.assertEqual(r3.collected_slots["district"], "Nellore")

        r4 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Rainfed", conv_id, language="en", farm_context={"growing_season": "Rabi (Winter)"}
        ))
        self.assertEqual(r4.routed_feature, "crop_advisor")
        self.assertIsNone(r4.pending_workflow)
        self.assertEqual(r4.feature_data["growing_season"], "Rabi (Winter)")
        self.assertNotEqual(r4.routed_feature, "market_prices")

    def test_crop_health_sequential_slot_filling(self):
        conv_id = "test_slot_health_1"
        clear_conversation_history(conv_id)

        # Turn 1: Farmer reports symptom without crop
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Lower leaves are turning yellow with brown spots",
            conv_id,
            language="en",
            farm_context={"district": "Warangal"}
        ))
        self.assertEqual(r1.pending_workflow, "crop_health")
        self.assertEqual(r1.next_slot, "crop_name")
        self.assertIn("Which crop are you currently growing", r1.reply_text)

        # Turn 2: Farmer supplies crop "Cotton"
        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Cotton",
            conv_id,
            language="en",
            farm_context={"district": "Warangal"}
        ))
        self.assertIsNone(r2.pending_workflow)
        self.assertEqual(r2.routed_feature, "crop_health")
        self.assertIsNotNone(r2.feature_data)
        self.assertIn("Cotton", r2.reply_text)
        self.assertIn("Safety Notice", r2.feature_data["safety_notice"])

    def test_workflow_cancellation(self):
        conv_id = "test_slot_cancel_1"
        clear_conversation_history(conv_id)

        # Turn 1: Initiate market price flow
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "Check mandi rate",
            conv_id,
            language="te",
            farm_context={"district": "Warangal"}
        ))
        self.assertEqual(r1.pending_workflow, "market_prices")

        # Turn 2: Farmer cancels
        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "రద్దు చేయండి",
            conv_id,
            language="te",
            farm_context={"district": "Warangal"}
        ))
        self.assertIsNone(r2.pending_workflow)
        self.assertIn("రద్దు చేసాను", r2.reply_text)

        # Session should be completely cleared
        sess = get_conversation_session(conv_id)
        self.assertIsNone(sess["pending_workflow"])

    def test_weather_missing_location_sequential_flow(self):
        conv_id = "test_slot_weather_missing_1"
        clear_conversation_history(conv_id)

        with patch("httpx.AsyncClient.get", new=mock_weather_http_get):

            # Turn 1: Farmer asks for weather without specifying district and empty farm context
            r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
                "Will it rain tomorrow?",
                conv_id,
                language="en",
                farm_context={}
            ))
            self.assertEqual(r1.pending_workflow, "weather")
            self.assertEqual(r1.next_slot, "district")
            self.assertIn("Which district's weather forecast", r1.reply_text)

            # Turn 2: Farmer supplies district "Khammam"
            r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
                "Khammam",
                conv_id,
                language="en",
                farm_context={}
            ))
            self.assertIsNone(r2.pending_workflow)
            self.assertEqual(r2.routed_feature, "weather")
            self.assertIsNotNone(r2.feature_data)
            self.assertIn("Khammam", r2.reply_text)
            self.assertEqual(r2.collected_slots.get("district"), "Khammam")

    def test_tomorrow_weather_question_uses_tomorrow_forecast(self):
        conv_id = "test_slot_weather_tomorrow_forecast"
        clear_conversation_history(conv_id)
        live_weather = WeatherData(
            district="Warangal",
            state="Telangana",
            temperature=24.0,
            feels_like=25.0,
            condition="Clear Sky",
            humidity=60,
            wind_speed=4.0,
            rain_probability=85,
            advisory="Today's advisory",
            irrigation_advice="Today's irrigation advice",
            spray_suitability="Check hourly forecast",
            produce_protection="Protect produce",
            source="WeatherAPI.com test fixture",
            forecast=[
                ForecastDay(day_name="Today", date="2026-11-06", temp_max=30, temp_min=20,
                            condition="Clear Sky", precipitation_probability=85),
                ForecastDay(day_name="Sat", date="2026-11-07", temp_max=29, temp_min=19,
                            condition="Partly Cloudy", precipitation_probability=0),
            ],
        )
        with patch("app.services.intent_router.WeatherService.get_district_weather", new_callable=AsyncMock) as get_weather:
            get_weather.return_value = live_weather
            result = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
                "Will it rain tomorrow in my district?",
                conv_id,
                language="en",
                farm_context={"district": "Warangal", "state": "Telangana"},
            ))

        self.assertEqual(result.routed_feature, "weather")
        self.assertIn("Tomorrow's forecast for Warangal (2026-11-07)", result.reply_text)
        self.assertIn("0% chance of rain", result.reply_text)
        self.assertNotIn("85%", result.reply_text)
        self.assertEqual(result.feature_data["source"], "WeatherAPI.com test fixture")

    def test_hindi_market_price_flow(self):
        conv_id = "test_slot_hi_1"
        clear_conversation_history(conv_id)

        # Turn 1: Farmer asks in Hindi "मंडी भाव बताओ"
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "आज का मंडी भाव बताओ",
            conv_id,
            language="hi",
            farm_context={}
        ))
        self.assertEqual(r1.pending_workflow, "market_prices")
        self.assertEqual(r1.next_slot, "commodity")
        self.assertIn("किस फसल", r1.reply_text)

        # Turn 2: Farmer says "मिर्च" (Chilli)
        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "मिर्च",
            conv_id,
            language="hi",
            farm_context={}
        ))
        self.assertEqual(r2.pending_workflow, "market_prices")
        self.assertEqual(r2.next_slot, "district")
        self.assertIn("जिला", r2.reply_text)

        # Turn 3: Farmer says "वारंगल" (Warangal)
        r3 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "वारंगल",
            conv_id,
            language="hi",
            farm_context={}
        ))
        self.assertIsNone(r3.pending_workflow)
        self.assertEqual(r3.routed_feature, "market_prices")
        self.assertIn("मिर्च", r3.reply_text)
        self.assertIn("DEMO", r3.reply_text)
        self.assertIn("उदाहरणात्मक", r3.reply_text)

    def test_kannada_crop_advisor_flow(self):
        conv_id = "test_slot_kn_1"
        clear_conversation_history(conv_id)

        # Turn 1: Farmer asks in Kannada "ಯಾವ ಬೆಳೆ ಬೆಳೆಯಬೇಕು?"
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "ಯಾವ ಬೆಳೆ ಬೆಳೆಯಬೇಕು?",
            conv_id,
            language="kn",
            farm_context={"district": "Warangal"}
        ))
        self.assertEqual(r1.pending_workflow, "crop_advisor")
        self.assertEqual(r1.next_slot, "soil_type")
        self.assertIn("ಮಣ್ಣಿನ ಪ್ರಕಾರ", r1.reply_text)

        # Turn 2: Farmer supplies "ಕಪ್ಪು ಮಣ್ಣು" (Black soil)
        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "ಕಪ್ಪು ಮಣ್ಣು",
            conv_id,
            language="kn",
            farm_context={"district": "Warangal"}
        ))
        self.assertEqual(r2.pending_workflow, "crop_advisor")
        self.assertEqual(r2.next_slot, "water_source")
        self.assertIn("ನೀರಾವರಿ ಸೌಲಭ್ಯ", r2.reply_text)

        # Turn 3: Farmer supplies "ಉತ್ತಮ ನೀರಾವರಿ" (Good irrigation)
        r3 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "ಉತ್ತಮ ನೀರಾವರಿ",
            conv_id,
            language="kn",
            farm_context={"district": "Warangal"}
        ))
        self.assertIsNone(r3.pending_workflow)
        self.assertEqual(r3.routed_feature, "crop_advisor")
        self.assertIsNotNone(r3.feature_data)

    def test_marathi_market_flow(self):
        conv_id = "test_slot_mr_1"
        clear_conversation_history(conv_id)

        # Turn 1: "बाजार भाव काय आहे?"
        r1 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "बाजार भाव काय आहे?",
            conv_id,
            language="mr",
            farm_context={}
        ))
        self.assertEqual(r1.pending_workflow, "market_prices")
        self.assertEqual(r1.next_slot, "commodity")

        # Turn 2: "कापूस" (Cotton)
        r2 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "कापूस",
            conv_id,
            language="mr",
            farm_context={}
        ))
        self.assertEqual(r2.pending_workflow, "market_prices")
        self.assertEqual(r2.next_slot, "district")

        # Turn 3: "वारंगळ" (Warangal)
        r3 = self.loop.run_until_complete(AssistantOrchestrator.process_user_query(
            "वारंगळ",
            conv_id,
            language="mr",
            farm_context={}
        ))
        self.assertIsNone(r3.pending_workflow)
        self.assertEqual(r3.routed_feature, "market_prices")
        self.assertIn("कापूस", r3.reply_text)
        self.assertIn("DEMO", r3.reply_text)
        self.assertIn("अधिकृत", r3.reply_text)
        self.assertIn("स्थिर उदाहरणार्थ", r3.reply_text)

if __name__ == "__main__":
    unittest.main()
