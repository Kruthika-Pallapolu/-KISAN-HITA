"""Server-issued authenticated browser sessions.

The browser receives only an opaque random token in an HttpOnly cookie. The
database stores its SHA-256 digest; client-supplied user IDs are never trusted.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status

from .config import settings
from .database import get_db_connection, cleanup_guest_session_data, cleanup_expired_guest_data

COOKIE_NAME = "kisan_session"
SESSION_TTL_DAYS = 30
GUEST_SESSION_TTL_HOURS = 24
logger = logging.getLogger(__name__)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _valid_session(request: Request):
    token = request.cookies.get(COOKIE_NAME, "")
    if not token or len(token) > 128:
        return None
    digest = _digest(token)
    conn = get_db_connection()
    row = conn.execute(
        "SELECT session_id, account_id, session_type, context_id, expires_at FROM browser_sessions WHERE session_id = ?",
        (digest,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    now = datetime.now(timezone.utc)
    try:
        expiry = datetime.fromisoformat(str(row["expires_at"]))
    except (TypeError, ValueError):
        expiry = now - timedelta(seconds=1)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now:
        if row["session_type"] == "guest":
            conn.close()
            cleanup_guest_session_data(digest)
            conn = get_db_connection()
        conn.execute("DELETE FROM browser_sessions WHERE session_id = ?", (digest,))
        conn.commit()
        conn.close()
        return None
    conn.execute("UPDATE browser_sessions SET last_seen_at = ? WHERE session_id = ?", (now.isoformat(), digest))
    conn.commit()
    conn.close()
    return {"session_id": digest, "account_id": row["account_id"], "session_type": row["session_type"], "context_id": row["context_id"]}


def issue_account_session(response: Response, account_id: str) -> None:
    token = secrets.token_urlsafe(32)
    digest = _digest(token)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=SESSION_TTL_DAYS)
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO browser_sessions (session_id, created_at, last_seen_at, expires_at, account_id) VALUES (?, ?, ?, ?, ?)",
        (digest, now.isoformat(), now.isoformat(), expires.isoformat(), account_id),
    )
    conn.commit()
    conn.close()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


def issue_guest_session(response: Response) -> str:
    """Issue a fresh opaque, 24-hour guest cookie and return its DB digest."""
    cleanup_expired_guest_data()
    token = secrets.token_urlsafe(32)
    digest = _digest(token)
    context_id = secrets.token_urlsafe(18)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=GUEST_SESSION_TTL_HOURS)
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO browser_sessions (session_id, created_at, last_seen_at, expires_at, account_id, session_type, context_id) VALUES (?, ?, ?, ?, NULL, 'guest', ?)",
            (digest, now.isoformat(), now.isoformat(), expires.isoformat(), context_id),
        )
        conn.commit()
    finally:
        conn.close()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=GUEST_SESSION_TTL_HOURS * 60 * 60,
        path="/",
    )
    return context_id


def revoke_request_session(request: Request, response: Response) -> None:
    session = _valid_session(request)
    if session:
        if session["session_type"] == "guest":
            cleanup_guest_session_data(session["session_id"])
        conn = get_db_connection()
        conn.execute("DELETE FROM browser_sessions WHERE session_id = ?", (session["session_id"],))
        conn.commit()
        conn.close()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=settings.COOKIE_SECURE, samesite="lax")


def require_same_origin(request: Request) -> None:
    """Reject cross-site state-changing browser requests when Origin is present."""
    origin = request.headers.get("origin")
    if not origin:
        return
    allowed = set(settings.allowed_origins_list)
    if origin not in allowed:
        logger.warning("Rejected state-changing request with untrusted Origin: %s", origin)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Untrusted request origin")


def current_session(request: Request) -> str:
    require_same_origin(request)
    session = _valid_session(request)
    if not session or session["session_type"] != "account" or not session["account_id"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return str(session["account_id"])


def current_farmer_session(request: Request) -> str:
    """Allow only account sessions or explicit, unexpired guest sessions."""
    require_same_origin(request)
    session = _valid_session(request)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Continue as a guest or sign in")
    if session["session_type"] == "account" and session["account_id"]:
        return str(session["account_id"])
    if session["session_type"] == "guest" and not session["account_id"]:
        return f"guest:{session['session_id']}"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid farmer session is required")
