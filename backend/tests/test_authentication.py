import os
import hashlib
import secrets
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app


class TestAccountAuthentication(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db = settings.DATABASE_PATH
        settings.DATABASE_PATH = os.path.join(self.temp_dir.name, "accounts.sqlite")

    def tearDown(self):
        settings.DATABASE_PATH = self.previous_db
        self.temp_dir.cleanup()

    def signup(self, client, email, lang="te", name="Chitti"):
        return client.post("/api/auth/signup", json={
            "email": email, "password": "correct-horse-42", "language": lang,
            "assistant_name": name,
        })

    def test_signup_hashes_password_sets_httponly_cookie_and_persists_preferences(self):
        with TestClient(app) as client:
            response = self.signup(client, "farmer@example.test")
            self.assertEqual(response.status_code, 201)
            self.assertTrue(client.cookies.get("kisan_session"))
            self.assertIn("httponly", response.headers.get("set-cookie", "").lower())
            profile = client.get("/api/settings/profile").json()
            self.assertEqual(profile["selected_language"], "te")
            self.assertEqual(profile["assistant_name"], "Chitti")
            self.assertTrue(profile["assistant_name_prompt_completed"])
            account = client.get("/api/auth/me").json()["user"]
            from backend.app.database import get_account_by_email
            stored = get_account_by_email("farmer@example.test")
            self.assertNotEqual(stored["password_hash"], "correct-horse-42")
            self.assertTrue(stored["password_hash"].startswith("scrypt$"))
            self.assertEqual(account["email"], "farmer@example.test")

    def test_duplicate_signup_login_logout_and_protected_routes(self):
        with TestClient(app) as first, TestClient(app) as second:
            self.assertEqual(self.signup(first, "same@example.test").status_code, 201)
            self.assertEqual(self.signup(second, "same@example.test").status_code, 409)
            self.assertEqual(second.get("/api/settings/profile").status_code, 401)
            self.assertEqual(second.get("/api/weather/districts").status_code, 401)
            self.assertEqual(second.post("/api/auth/login", json={"email": "same@example.test", "password": "wrong-password"}).status_code, 401)
            self.assertEqual(second.post("/api/auth/login", json={"email": "same@example.test", "password": "correct-horse-42"}).status_code, 200)
            self.assertEqual(second.get("/api/settings/profile").status_code, 200)
            self.assertEqual(second.post("/api/auth/logout").status_code, 200)
            self.assertEqual(second.get("/api/settings/profile").status_code, 401)

    def test_password_validation_never_echoes_password(self):
        secret = "bad-pass"
        with TestClient(app) as client:
            response = client.post("/api/auth/signup", json={
                "email": "short@example.test", "password": secret,
            })
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(secret, response.text)

    def test_conversations_are_isolated_by_account(self):
        with TestClient(app) as farmer_a, TestClient(app) as farmer_b:
            self.signup(farmer_a, "a@example.test", "en", "Kisan Assistant")
            self.signup(farmer_b, "b@example.test", "hi", "Mitra")
            response = farmer_a.post("/api/assistant/chat", json={
                "message": "Hello", "conversation_id": "private_account_conversation", "language": "en",
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(farmer_b.get("/api/assistant/history/private_account_conversation").status_code, 404)

    def test_expired_cookie_session_is_rejected(self):
        with TestClient(app) as client:
            self.signup(client, "expired@example.test")
            token = client.cookies.get("kisan_session")
            digest = hashlib.sha256(token.encode()).hexdigest()
            from backend.app.database import get_db_connection
            conn = get_db_connection()
            conn.execute("UPDATE browser_sessions SET expires_at = ? WHERE session_id = ?", ("2000-01-01T00:00:00+00:00", digest))
            conn.commit()
            conn.close()
            self.assertEqual(client.get("/api/settings/profile").status_code, 401)
            self.assertFalse(client.get("/api/auth/me").json()["authenticated"])

    def test_signup_migrates_current_anonymous_profile_and_conversation(self):
        from backend.app.database import get_db_connection, update_user_profile, save_conversation_message
        token = secrets.token_urlsafe(32)
        session_id = hashlib.sha256(token.encode()).hexdigest()
        with TestClient(app) as client:
            now = "2026-11-07T00:00:00+00:00"
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO browser_sessions (session_id, created_at, last_seen_at, expires_at, account_id) VALUES (?, ?, ?, ?, NULL)",
                (session_id, now, now, "2099-11-07T00:00:00+00:00"),
            )
            conn.commit()
            conn.close()
            update_user_profile(session_id, {"district": "Nellore", "state": "Andhra Pradesh", "selected_language": "mr"})
            save_conversation_message("legacy_before_signup", "user", "Keep this conversation", owner_id=session_id)
            client.cookies.set("kisan_session", token)
            response = client.post("/api/auth/signup", json={
                "email": "migrated@example.test", "password": "correct-horse-42",
                "language": "en", "assistant_name": "Chitti",
            })
            self.assertEqual(response.status_code, 201)
            self.assertTrue(response.json()["legacy_session_migrated"])
            profile = client.get("/api/settings/profile").json()
            self.assertEqual(profile["district"], "Nellore")
            self.assertEqual(profile["state"], "Andhra Pradesh")
            self.assertEqual(profile["selected_language"], "en")
            self.assertEqual(profile["assistant_name"], "Chitti")
            history = client.get("/api/assistant/history/legacy_before_signup")
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json()[0]["text"], "Keep this conversation")


if __name__ == "__main__":
    unittest.main()
