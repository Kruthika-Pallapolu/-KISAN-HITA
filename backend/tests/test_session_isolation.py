import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.tests.auth_helpers import sign_up


class TestAnonymousSessionIsolation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db = settings.DATABASE_PATH
        settings.DATABASE_PATH = os.path.join(self.temp_dir.name, "sessions.sqlite")

    def tearDown(self):
        settings.DATABASE_PATH = self.previous_db
        self.temp_dir.cleanup()

    def test_profiles_are_isolated_between_browser_sessions(self):
        with TestClient(app) as farmer_a, TestClient(app) as farmer_b:
            sign_up(farmer_a)
            sign_up(farmer_b)
            self.assertEqual(farmer_a.get("/api/settings/profile").status_code, 200)
            self.assertEqual(farmer_b.get("/api/settings/profile").status_code, 200)
            self.assertNotEqual(farmer_a.cookies.get("kisan_session"), farmer_b.cookies.get("kisan_session"))

            farmer_a.post("/api/settings/profile", json={"district": "Nellore"})
            farmer_b.post("/api/settings/profile", json={"district": "Warangal"})

            self.assertEqual(farmer_a.get("/api/settings/profile").json()["district"], "Nellore")
            self.assertEqual(farmer_b.get("/api/settings/profile").json()["district"], "Warangal")

    def test_assistant_name_onboarding_completion_is_saved_per_session(self):
        with TestClient(app) as farmer_a, TestClient(app) as farmer_b:
            sign_up(farmer_a)
            sign_up(farmer_b)
            response = farmer_a.post("/api/settings/profile", json={
                "assistant_name": "Chitti",
                "assistant_name_prompt_completed": True,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(farmer_a.get("/api/settings/profile").json()["assistant_name"], "Chitti")
            self.assertTrue(farmer_a.get("/api/settings/profile").json()["assistant_name_prompt_completed"])
            self.assertEqual(farmer_b.get("/api/settings/profile").json()["assistant_name"], "Nikki Samhita")
            self.assertFalse(farmer_b.get("/api/settings/profile").json()["assistant_name_prompt_completed"])

    def test_conversation_cannot_be_read_or_cleared_by_another_session(self):
        with TestClient(app) as farmer_a, TestClient(app) as farmer_b:
            sign_up(farmer_a)
            sign_up(farmer_b)
            response = farmer_a.post(
                "/api/assistant/chat",
                json={"message": "Hello", "conversation_id": "private_conversation", "language": "en"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                farmer_b.get("/api/assistant/history/private_conversation").status_code,
                404,
            )
            self.assertEqual(
                farmer_b.post("/api/assistant/clear/private_conversation").status_code,
                404,
            )
            self.assertEqual(
                farmer_a.get("/api/assistant/history/private_conversation").status_code,
                200,
            )

    def test_chat_recovers_from_stale_conversation_id_without_cross_session_history(self):
        stale_id = "conv_stale_browser_session"
        with TestClient(app) as farmer_a, TestClient(app) as farmer_b:
            sign_up(farmer_a)
            sign_up(farmer_b)
            first = farmer_a.post("/api/assistant/chat", json={
                "message": "Which crop suits black cotton soil?",
                "conversation_id": stale_id,
                "language": "en",
                "farm_context": {"soil_type": "Black Cotton Soil"},
            })
            self.assertEqual(first.status_code, 200)

            recovered = farmer_b.post("/api/assistant/chat", json={
                "message": "Will it rain tomorrow in my district?",
                "conversation_id": stale_id,
                "language": "en",
                "farm_context": {},
            })
            self.assertEqual(recovered.status_code, 200)
            fresh_id = recovered.json()["conversation_id"]
            self.assertNotEqual(fresh_id, stale_id)
            self.assertEqual(recovered.json()["intent"], "weather")
            self.assertEqual(recovered.json()["next_slot"], "district")

            farmer_b_history = farmer_b.get(f"/api/assistant/history/{fresh_id}")
            farmer_a_history = farmer_a.get(f"/api/assistant/history/{stale_id}")
            self.assertEqual(farmer_b_history.status_code, 200)
            self.assertEqual(farmer_a_history.status_code, 200)
            self.assertEqual([message["text"] for message in farmer_b_history.json() if message["sender"] == "user"], [
                "Will it rain tomorrow in my district?",
            ])
            self.assertEqual([message["text"] for message in farmer_a_history.json() if message["sender"] == "user"], [
                "Which crop suits black cotton soil?",
            ])

    def test_new_voice_question_interrupts_pending_workflow_as_a_separate_message(self):
        conversation_id = "conv_separate_voice_questions"
        with TestClient(app) as farmer:
            sign_up(farmer)
            first = farmer.post("/api/assistant/chat", json={
                "message": "Which crop suits black cotton soil?",
                "conversation_id": conversation_id,
                "language": "en",
                "farm_context": {"soil_type": "Black Cotton Soil"},
            })
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()["next_slot"], "district")

            second = farmer.post("/api/assistant/chat", json={
                "message": "Will it rain tomorrow in my district?",
                "conversation_id": conversation_id,
                "language": "en",
                "farm_context": {},
            })
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.json()["intent"], "weather")
            self.assertEqual(second.json()["next_slot"], "district")
            self.assertIn("Which district", second.json()["reply_text"])

            history = farmer.get(f"/api/assistant/history/{conversation_id}")
            self.assertEqual(history.status_code, 200)
            user_messages = [message["text"] for message in history.json() if message["sender"] == "user"]
            self.assertEqual(user_messages, [
                "Which crop suits black cotton soil?",
                "Will it rain tomorrow in my district?",
            ])

    def test_repeated_crop_question_is_not_misread_as_irrigation_answer(self):
        conversation_id = "conv_repeated_crop_question"
        question = "Which crop suits black cotton soil?"
        with TestClient(app) as farmer:
            sign_up(farmer)
            replies = [farmer.post("/api/assistant/chat", json={
                "message": question,
                "conversation_id": conversation_id,
                "language": "en",
                "farm_context": {},
            }) for _ in range(2)]
            self.assertEqual([response.status_code for response in replies], [200, 200])
            self.assertEqual([response.json()["intent"] for response in replies], ["crop_advisor", "crop_advisor"])
            self.assertEqual([response.json()["next_slot"] for response in replies], ["district", "district"])
            self.assertTrue(all(response.json()["collected_slots"].get("soil_type") == "Black Cotton Soil" for response in replies))

    def test_chat_allows_configured_frontend_origin_and_rejects_untrusted_origin(self):
        configured_origin = settings.allowed_origins_list[0]
        with TestClient(app) as farmer:
            sign_up(farmer)
            profile = farmer.get("/api/settings/profile", headers={"Origin": configured_origin})
            self.assertEqual(profile.status_code, 200)
            self.assertIsNotNone(farmer.cookies.get("kisan_session"))

            accepted = farmer.post("/api/assistant/chat", headers={"Origin": configured_origin}, json={
                "message": "Which crop suits black cotton soil?",
                "conversation_id": "conv_origin_allowed",
                "language": "en",
                "farm_context": {"soil_type": "Black Cotton Soil"},
            })
            self.assertEqual(accepted.status_code, 200)

            rejected = farmer.post("/api/assistant/chat", headers={"Origin": "https://untrusted.invalid"}, json={
                "message": "Which crop suits black cotton soil?",
                "conversation_id": "conv_origin_rejected",
                "language": "en",
                "farm_context": {},
            })
            self.assertEqual(rejected.status_code, 403)
            self.assertEqual(rejected.json(), {"detail": "Untrusted request origin"})

    def test_mobile_lan_origin_can_start_guest_session_and_untrusted_origin_stays_rejected(self):
        previous_mobile_origin = "http://192.168.29.3:5173"
        current_mobile_origin = "http://192.168.29.52:5173"
        with TestClient(app) as client:
            created = client.post("/api/auth/guest", headers={"Origin": previous_mobile_origin})
            self.assertEqual(created.status_code, 200, created.text)
            self.assertEqual(created.json().get("mode"), "guest")
            self.assertEqual(created.headers.get("access-control-allow-origin"), previous_mobile_origin)
            self.assertTrue(client.cookies.get("kisan_session"))
            try:
                session = client.get("/api/auth/session", headers={"Origin": current_mobile_origin})
                self.assertEqual(session.status_code, 200)
                self.assertEqual(session.json().get("mode"), "guest")
                self.assertEqual(session.headers.get("access-control-allow-origin"), current_mobile_origin)

                rejected = client.post("/api/auth/guest", headers={"Origin": "https://untrusted.invalid"})
                self.assertEqual(rejected.status_code, 403)
                self.assertEqual(rejected.json(), {"detail": "Untrusted request origin"})
            finally:
                ended = client.post("/api/auth/guest/end", headers={"Origin": current_mobile_origin})
                self.assertEqual(ended.status_code, 200, ended.text)

            signup = client.post("/api/auth/signup", headers={"Origin": current_mobile_origin}, json={
                "email": "mobile-origin-signup@example.test",
                "password": "test-password-123",
                "language": "en",
            })
            self.assertEqual(signup.status_code, 201, signup.text)
            self.assertEqual(signup.headers.get("access-control-allow-origin"), current_mobile_origin)
            self.assertTrue(client.cookies.get("kisan_session"))
            session = client.get("/api/auth/session")
            self.assertEqual(session.status_code, 200)
            self.assertEqual(session.json().get("mode"), "account")


if __name__ == "__main__":
    unittest.main()
