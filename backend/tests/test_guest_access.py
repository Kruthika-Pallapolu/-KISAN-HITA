import base64
import hashlib
import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.config import settings
from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.services.market_service import MarketPriceService


class TestGuestAccess(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db = settings.DATABASE_PATH
        settings.DATABASE_PATH = os.path.join(self.temp_dir.name, "guest.sqlite")
        init_db()

    def tearDown(self):
        settings.DATABASE_PATH = self.previous_db
        self.temp_dir.cleanup()

    def guest(self):
        client = TestClient(app)
        response = client.post("/api/auth/guest")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["mode"], "guest")
        self.assertTrue(client.cookies.get("kisan_session"))
        self.assertIn("httponly", response.headers.get("set-cookie", "").lower())
        return client, response.json()["context_id"]

    def test_guest_can_use_farmer_features_and_account_routes_stay_protected(self):
        with TestClient(app) as client:
            created = client.post("/api/auth/guest")
            self.assertEqual(created.status_code, 200, created.text)
            self.assertEqual(client.get("/api/auth/session").json()["mode"], "guest")

            crop = client.post("/api/crop-advisor/recommend", json={
                "soil_type": "Black Cotton Soil", "water_availability": "Good irrigation",
                "growing_season": "Kharif (Monsoon)", "district": "Nellore",
                "state": "Andhra Pradesh", "language": "en",
            })
            self.assertEqual(crop.status_code, 200, crop.text)
            self.assertIn("DEMO", crop.json()["disclaimer"].upper())

            health = client.post("/api/crop-health/diagnose", json={
                "crop_name": "Cotton", "symptoms": "yellow leaves with spots", "language": "en",
            })
            self.assertEqual(health.status_code, 200, health.text)

            image_buffer = io.BytesIO()
            Image.new("RGB", (12, 12), color=(30, 120, 40)).save(image_buffer, format="JPEG")
            image_check = client.post("/api/crop-health/diagnose", json={
                "crop_name": "Cotton", "symptoms": "yellow leaves with spots",
                "image_base64": base64.b64encode(image_buffer.getvalue()).decode("ascii"), "language": "en",
            })
            self.assertEqual(image_check.status_code, 200, image_check.text)
            self.assertEqual(image_check.json()["visual_analysis_status"], "unavailable")
            self.assertFalse(image_check.json().get("ai_observations"))

            market = client.get("/api/market-prices/search", params={
                "commodity": "Chilli", "district": "Guntur", "state": "Andhra Pradesh", "language": "en",
            })
            self.assertEqual(market.status_code, 200, market.text)
            self.assertTrue(market.json()["records"])
            self.assertEqual(market.json()["records"][0]["unit"], "kg")
            self.assertFalse(market.json()["is_live_api"])
            self.assertEqual(market.json()["data_type"], "illustrative")

            chat = client.post("/api/assistant/chat", json={
                "message": "Which crop suits black cotton soil?", "language": "en",
                "farm_context": {"soil_type": "Black Cotton Soil", "water_source": "Good irrigation"},
            })
            self.assertEqual(chat.status_code, 200, chat.text)
            self.assertTrue(chat.json()["reply_text"])

            crop_chat = client.post("/api/assistant/chat", json={
                "message": "Which crops may suit black cotton soil in Nellore with rainfed conditions during Rabi?",
                "language": "en",
                "farm_context": {
                    "district": "Nellore", "state": "Andhra Pradesh", "soil_type": "Black Cotton Soil",
                    "water_source": "Rain-dependent", "growing_season": "Rabi (Winter)",
                },
            })
            self.assertEqual(crop_chat.status_code, 200, crop_chat.text)
            crop_reply = crop_chat.json()["reply_text"]
            self.assertIn("Bengal Gram", crop_reply)
            self.assertIn("Black Gram", crop_reply)
            self.assertIn("general suggestions, not verified for your field", crop_reply)
            self.assertIn("local KVK", crop_reply)
            self.assertNotIn("DEMO", crop_reply.upper())

            self.assertEqual(client.get("/api/settings/profile").status_code, 401)
            self.assertEqual(client.post("/api/settings/test-ai").status_code, 401)
            voice_config = client.get("/api/voice/config")
            self.assertEqual(voice_config.status_code, 200)
            self.assertFalse(voice_config.json()["prisma_enabled"])
            self.assertFalse(voice_config.json()["timbre_enabled"])
            self.assertNotIn("api_key", voice_config.json())
            self.assertEqual(client.post("/api/auth/logout").status_code, 401)
            self.assertEqual(client.get("/api/auth/me").json()["authenticated"], False)
            # This machine has a verified local English system voice. Assert
            # that guest TTS returns actual audio bytes, never an empty success.
            tts = client.post("/api/voice/tts", json={"text": "Hello farmer", "language": "en"})
            self.assertEqual(tts.status_code, 200, tts.text)
            audio = base64.b64decode(tts.json()["audio_base64"])
            self.assertGreaterEqual(len(audio), 44)
            self.assertFalse(tts.json()["is_mock"])

    def test_guest_sessions_are_isolated_from_each_other_and_accounts(self):
        first, first_context = self.guest()
        second, second_context = self.guest()
        self.assertNotEqual(first_context, second_context)
        with TestClient(app) as account:
            self.assertEqual(account.post("/api/auth/signup", json={
                "email": "private-account@example.test", "password": "correct-horse-42", "language": "en",
            }).status_code, 201)
            account_chat = account.post("/api/assistant/chat", json={
                "message": "Hello", "conversation_id": "account_private_case_1", "language": "en",
            })
            self.assertEqual(account_chat.status_code, 200, account_chat.text)
            self.assertEqual(first.get("/api/assistant/history/account_private_case_1").status_code, 404)
        conversation_id = "guest_private_case_1"
        response = first.post("/api/assistant/chat", json={
            "message": "Which crop suits black cotton soil?", "conversation_id": conversation_id, "language": "en",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(second.get(f"/api/assistant/history/{conversation_id}").status_code, 404)

        signup = first.post("/api/auth/signup", json={
            "email": "guest-signup@example.test", "password": "correct-horse-42", "language": "en",
        })
        self.assertEqual(signup.status_code, 201, signup.text)
        # Guest conversation is not silently migrated into the new account.
        self.assertEqual(first.get(f"/api/assistant/history/{conversation_id}").status_code, 404)
        self.assertEqual(first.get("/api/settings/profile").status_code, 200)
        self.assertEqual(second.get("/api/auth/session").json()["mode"], "guest")

    def test_guest_creation_has_a_shared_ip_rate_limit(self):
        clients = [TestClient(app) for _ in range(6)]
        responses = [client.post("/api/auth/guest") for client in clients]
        self.assertEqual([response.status_code for response in responses[:5]], [200] * 5)
        self.assertEqual(responses[5].status_code, 429)

    def test_crop_advisor_voice_turns_continue_on_the_same_chat_endpoint(self):
        with TestClient(app) as client:
            client.post("/api/auth/guest")
            conversation_id = "guest_voice_crop_followup"
            turns = [
                ("Help me choose a crop", "district"),
                ("Nellore", "soil_type"),
                ("Black soil", "water_source"),
            ]
            for message, next_slot in turns:
                response = client.post("/api/assistant/chat", json={
                    "message": message,
                    "conversation_id": conversation_id,
                    "language": "en",
                })
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["conversation_id"], conversation_id)
                self.assertEqual(data["routed_feature"], "crop_advisor")
                self.assertEqual(data["pending_workflow"], "crop_advisor")
                self.assertEqual(data["next_slot"], next_slot)
            final = client.post("/api/assistant/chat", json={
                "message": "Rainfed",
                "conversation_id": conversation_id,
                "language": "en",
            })
            self.assertEqual(final.status_code, 200, final.text)
            result = final.json()
            self.assertEqual(result["conversation_id"], conversation_id)
            self.assertEqual(result["routed_feature"], "crop_advisor")
            self.assertIsNone(result["pending_workflow"])
            self.assertEqual(result["collected_slots"]["district"], "Nellore")
            self.assertNotEqual(result["routed_feature"], "market_prices")

    def test_expired_guest_is_not_renewed_and_cleanup_is_session_scoped(self):
        first, _ = self.guest()
        second, _ = self.guest()
        first_chat = first.post("/api/assistant/chat", json={
            "message": "Hello", "conversation_id": "expired_guest_conversation", "language": "en",
        })
        second_chat = second.post("/api/assistant/chat", json={
            "message": "Hello", "conversation_id": "active_guest_conversation", "language": "en",
        })
        self.assertEqual(first_chat.status_code, 200, first_chat.text)
        self.assertEqual(second_chat.status_code, 200, second_chat.text)

        token = first.cookies.get("kisan_session")
        digest = hashlib.sha256(token.encode()).hexdigest()
        conn = get_db_connection()
        conn.execute("UPDATE browser_sessions SET expires_at = ? WHERE session_id = ?", ((datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat(), digest))
        conn.commit()
        conn.close()

        status = first.get("/api/auth/session")
        self.assertEqual(status.json()["mode"], "none")
        self.assertNotIn("set-cookie", status.headers)
        self.assertEqual(first.post("/api/auth/guest").json()["mode"], "guest")  # only explicit creation renews
        self.assertEqual(second.get("/api/assistant/history/active_guest_conversation").status_code, 200)
        self.assertEqual(first.get("/api/assistant/history/expired_guest_conversation").status_code, 404)
        conn = get_db_connection()
        self.assertIsNone(conn.execute("SELECT 1 FROM conversations WHERE id = ?", ("expired_guest_conversation",)).fetchone())
        self.assertIsNotNone(conn.execute("SELECT 1 FROM conversations WHERE id = ?", ("active_guest_conversation",)).fetchone())
        conn.close()

    def test_all_supported_guest_locales_can_use_chat(self):
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/auth/guest").status_code, 200)
            for language in ("en", "te", "hi", "ta", "kn", "ml", "mr"):
                response = client.post("/api/assistant/chat", json={"message": "Hello", "language": language})
                self.assertEqual(response.status_code, 200, f"{language}: {response.text}")
                self.assertEqual(response.json()["language"], language)
