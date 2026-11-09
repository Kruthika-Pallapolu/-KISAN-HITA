"""Cookie-based account authentication for Kisan Hita."""
import hashlib
import hmac
import re
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from ..auth import current_session, issue_account_session, issue_guest_session, require_same_origin, revoke_request_session, _valid_session
from ..database import DEFAULT_ASSISTANT_NAME, create_account, get_account_by_email, get_account_by_id, save_account_profile, migrate_anonymous_session_data
from ..rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/auth", tags=["authentication"])
_PASSWORD_N = 1 << 14


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_PASSWORD_N, r=8, p=1, dklen=32)
    return f"scrypt${_PASSWORD_N}$8$1${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(hash_hex)),
        )
        return hmac.compare_digest(actual, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    # Length is checked inside the endpoint so FastAPI's validation payload
    # never echoes a submitted password back to the browser.
    password: str
    language: str = Field("te", max_length=2)
    assistant_name: str | None = Field(None, min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"te", "en", "hi", "ta", "kn", "ml", "mr"}:
            raise ValueError("Unsupported language")
        return value

    @field_validator("assistant_name")
    @classmethod
    def normalize_assistant_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Assistant name is required")
        return value


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


def _account_payload(account_id: str):
    account = get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again.")
    return {"authenticated": True, "user": {"id": account["id"], "email": account["email"]}}


@router.get("/me")
async def who_am_i(request: Request):
    from ..auth import _valid_session
    session = _valid_session(request)
    if not session or not session["account_id"]:
        return {"authenticated": False, "user": None}
    try:
        return _account_payload(str(session["account_id"]))
    except HTTPException:
        return {"authenticated": False, "user": None}


@router.get("/session")
async def session_status(request: Request):
    session = _valid_session(request)
    if not session:
        return {"mode": "none"}
    if session["session_type"] == "account" and session["account_id"]:
        return {"mode": "account"}
    if session["session_type"] == "guest" and not session["account_id"]:
        return {"mode": "guest", "context_id": session["context_id"]}
    return {"mode": "none"}


@router.post("/guest")
async def create_guest_session(request: Request, response: Response):
    require_same_origin(request)
    enforce_rate_limit(request, "guest-session-create-burst-ip", 5, 60)
    enforce_rate_limit(request, "guest-session-create-ip", 30, 60 * 60)
    existing = _valid_session(request)
    if existing and existing["session_type"] == "account" and existing["account_id"]:
        return {"mode": "account"}
    if existing and existing["session_type"] == "guest":
        return {"mode": "guest", "context_id": existing["context_id"], "expires_in_seconds": 24 * 60 * 60}
    context_id = issue_guest_session(response)
    return {"mode": "guest", "context_id": context_id, "expires_in_seconds": 24 * 60 * 60}


@router.post("/guest/end")
async def end_guest_session(request: Request, response: Response):
    require_same_origin(request)
    session = _valid_session(request)
    if session and session["session_type"] == "account":
        raise HTTPException(status_code=409, detail="Signed-in account sessions cannot be ended as guest sessions")
    if session and session["session_type"] == "guest":
        from ..database import cleanup_guest_session_data, get_db_connection
        cleanup_guest_session_data(session["session_id"])
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM browser_sessions WHERE session_id = ? AND session_type = 'guest'", (session["session_id"],))
            conn.commit()
        finally:
            conn.close()
    from ..config import settings
    response.delete_cookie("kisan_session", path="/", httponly=True, secure=settings.COOKIE_SECURE, samesite="lax")
    return {"mode": "none"}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, request: Request, response: Response):
    require_same_origin(request)
    enforce_rate_limit(request, "auth-signup", 5, 60)
    if not 10 <= len(data.password) <= 128:
        raise HTTPException(status_code=422, detail="Password must be between 10 and 128 characters.")
    if get_account_by_email(data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    account_id = f"acct_{uuid.uuid4().hex}"
    previous_session = _valid_session(request)
    try:
        create_account(data.email, _hash_password(data.password), account_id)
    except Exception as exc:
        # Handle a concurrent signup for the same normalized email.
        if get_account_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from exc
        raise
    migrated_legacy_session = bool(
        previous_session
        and previous_session["session_type"] == "account"
        and not previous_session["account_id"]
        and migrate_anonymous_session_data(previous_session["session_id"], account_id)
    )
    assistant_name = data.assistant_name or DEFAULT_ASSISTANT_NAME
    save_account_profile(account_id, {
        "selected_language": data.language,
        "assistant_name": assistant_name,
        "assistant_name_prompt_completed": bool(data.assistant_name),
    })
    revoke_request_session(request, response)
    issue_account_session(response, account_id)
    return {**_account_payload(account_id), "legacy_session_migrated": migrated_legacy_session}


@router.post("/login")
async def login(data: LoginRequest, request: Request, response: Response):
    require_same_origin(request)
    enforce_rate_limit(request, "auth-login", 10, 60)
    if not data.password or len(data.password) > 128:
        raise HTTPException(status_code=422, detail="Enter a valid password.")
    account = get_account_by_email(data.email)
    if not account or not _verify_password(data.password, account["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")
    revoke_request_session(request, response)
    issue_account_session(response, account["id"])
    return _account_payload(account["id"])


@router.post("/logout")
async def logout(request: Request, response: Response, account_id: str = Depends(current_session)):
    revoke_request_session(request, response)
    return {"status": "signed_out"}

