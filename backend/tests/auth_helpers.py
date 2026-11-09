import uuid
import sqlite3
from fastapi.testclient import TestClient


def authenticated_client(app, *, language="en", assistant_name=None):
    client = TestClient(app)
    sign_up(client, language=language, assistant_name=assistant_name)
    return client


def sign_up(client, *, language="en", assistant_name=None):
    # Each test account is independent; clear only the auth-signup limiter so
    # suite order and repeated runs don't exhaust a shared local test DB.
    from backend.app.config import settings
    try:
        with sqlite3.connect(settings.DATABASE_PATH) as connection:
            connection.execute("DELETE FROM api_rate_limits WHERE rate_key LIKE 'auth-signup:%'")
    except sqlite3.Error:
        pass
    data = {
        "email": f"{uuid.uuid4().hex}@example.test",
        "password": "test-password-strong-123",
        "language": language,
    }
    if assistant_name is not None:
        data["assistant_name"] = assistant_name
    response = client.post("/api/auth/signup", json=data)
    assert response.status_code == 201, response.text
