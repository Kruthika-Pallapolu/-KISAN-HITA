import sqlite3
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from .config import settings

DEFAULT_ASSISTANT_NAME = "Nikki Samhita"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_db_connection():
    """
    Acquires an SQLite connection with:
    - 30-second busy timeout to prevent 'database is locked' errors.
    - Write-Ahead Logging (WAL) for concurrent read/write support.
    - Explicit foreign key constraint enforcement.
    """
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        
        # User Profile & Preferences (no fabricated location or agronomic defaults)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id TEXT PRIMARY KEY,
            selected_language TEXT DEFAULT 'te',
            assistant_name TEXT DEFAULT 'Nikki Samhita',
            assistant_name_prompt_completed INTEGER NOT NULL DEFAULT 0,
            state TEXT DEFAULT NULL,
            district TEXT DEFAULT NULL,
            village TEXT DEFAULT '',
            soil_type TEXT DEFAULT NULL,
            water_source TEXT DEFAULT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        profile_columns = {r["name"] for r in cursor.execute("PRAGMA table_info(user_profiles)")}
        if "assistant_name_prompt_completed" not in profile_columns:
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN assistant_name_prompt_completed INTEGER NOT NULL DEFAULT 0")
        
        # Browser sessions store only a digest of the HttpOnly cookie token.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS browser_sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            account_id TEXT,
            session_type TEXT NOT NULL DEFAULT 'account',
            context_id TEXT
        );
        """)
        session_columns = {r["name"] for r in cursor.execute("PRAGMA table_info(browser_sessions)")}
        if "account_id" not in session_columns:
            cursor.execute("ALTER TABLE browser_sessions ADD COLUMN account_id TEXT")
        if "session_type" not in session_columns:
            cursor.execute("ALTER TABLE browser_sessions ADD COLUMN session_type TEXT NOT NULL DEFAULT 'account'")
        if "context_id" not in session_columns:
            cursor.execute("ALTER TABLE browser_sessions ADD COLUMN context_id TEXT")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # Conversations are owned by a server-issued browser session.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'guest',
            owner_session_id TEXT,
            language TEXT DEFAULT 'te',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conversation_columns = {r["name"] for r in cursor.execute("PRAGMA table_info(conversations)")}
        if "owner_session_id" not in conversation_columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN owner_session_id TEXT")
        
        # Messages
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            text TEXT NOT NULL,
            intent TEXT DEFAULT 'general',
            feature TEXT DEFAULT 'assistant',
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        """)

        # Conversation Sessions for Multi-Turn Slot Filling
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            conversation_id TEXT PRIMARY KEY,
            pending_workflow TEXT,
            collected_slots_json TEXT DEFAULT '{}',
            missing_slots_json TEXT DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Performance and security indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON conversation_sessions(updated_at);")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_rate_limits (
            rate_key TEXT PRIMARY KEY,
            window_started INTEGER NOT NULL,
            request_count INTEGER NOT NULL
        )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations(owner_session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_browser_sessions_expiry ON browser_sessions(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_browser_sessions_account ON browser_sessions(account_id)")
        # Legacy guest records are deliberately left unowned and inaccessible to new sessions.
            
    conn.close()

def create_account(email: str, password_hash: str, account_id: str) -> None:
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO accounts (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (account_id, email, password_hash, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

def get_account_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute("SELECT id, email, password_hash FROM accounts WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute("SELECT id, email FROM accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def save_account_profile(account_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    return update_user_profile(account_id, updates)

def migrate_anonymous_session_data(anonymous_session_id: str, account_id: str) -> bool:
    """Move the current browser's old anonymous profile/history into its new account."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM user_profiles WHERE id = ?", (anonymous_session_id,)).fetchone()
    profile = dict(row) if row else None
    conn.close()
    if profile:
        update_user_profile(account_id, {
            key: profile[key] for key in (
                "selected_language", "assistant_name", "assistant_name_prompt_completed",
                "state", "district", "village", "soil_type", "water_source",
            ) if key in profile
        })
        conn = get_db_connection()
        conn.execute("DELETE FROM user_profiles WHERE id = ?", (anonymous_session_id,))
    else:
        conn = get_db_connection()
    moved = conn.execute(
        "UPDATE conversations SET owner_session_id = ?, user_id = ? WHERE owner_session_id = ?",
        (account_id, account_id, anonymous_session_id),
    ).rowcount
    conn.commit()
    conn.close()
    return bool(row or moved)


def cleanup_guest_session_data(session_id: str) -> None:
    """Delete only data owned by one explicit guest session."""
    owner_id = f"guest:{session_id}"
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conversation_ids = [r[0] for r in conn.execute(
            "SELECT id FROM conversations WHERE owner_session_id = ?", (owner_id,)
        ).fetchall()]
        if conversation_ids:
            placeholders = ",".join("?" for _ in conversation_ids)
            conn.execute(
                f"DELETE FROM conversation_sessions WHERE conversation_id IN ({placeholders})",
                conversation_ids,
            )
            conn.execute("DELETE FROM conversations WHERE owner_session_id = ?", (owner_id,))
        for scope in ("assistant-chat", "assistant-image", "crop-health", "crop-health-image"):
            conn.execute("DELETE FROM api_rate_limits WHERE rate_key = ?", (f"{scope}:{owner_id}",))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cleanup_expired_guest_data(now: Optional[datetime] = None) -> int:
    """Purge expired explicit guest sessions and their owned data only."""
    moment = now or datetime.now(timezone.utc)
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT session_id FROM browser_sessions WHERE session_type = 'guest' AND expires_at <= ?",
            (moment.isoformat(),),
        ).fetchall()
        session_ids = [str(row["session_id"]) for row in rows]
    finally:
        conn.close()
    for session_id in session_ids:
        cleanup_guest_session_data(session_id)
        conn = get_db_connection()
        try:
            conn.execute(
                "DELETE FROM browser_sessions WHERE session_id = ? AND session_type = 'guest' AND expires_at <= ?",
                (session_id, moment.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
    return len(session_ids)

def get_user_profile(user_id: str = "guest") -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profiles WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "id": user_id,
        "selected_language": "te",
        "assistant_name": DEFAULT_ASSISTANT_NAME,
        "assistant_name_prompt_completed": 0,
        "state": None,
        "district": None,
        "village": "",
        "soil_type": None,
        "water_source": None,
    }

def update_user_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        
        # Ensure profile row exists
        cursor.execute("SELECT id FROM user_profiles WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO user_profiles (id, selected_language, assistant_name, assistant_name_prompt_completed, state, district, village, soil_type, water_source)
            VALUES (?, 'te', 'Nikki Samhita', 0, NULL, NULL, '', NULL, NULL)
            """, (user_id,))
        
        fields = []
        values = []
        allowed_keys = ["selected_language", "assistant_name", "assistant_name_prompt_completed", "state", "district", "village", "soil_type", "water_source"]
        for k in allowed_keys:
            if k in updates:
                fields.append(f"{k} = ?")
                values.append(updates[k])
                
        if fields:
            fields.append("updated_at = ?")
            values.append(now_iso())
            values.append(user_id)
            sql = f"UPDATE user_profiles SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(sql, values)
            
    conn.close()
    return get_user_profile(user_id)

def _sanitize_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Strips large binary/base64 image payloads from stored message metadata."""
    if not meta or not isinstance(meta, dict):
        return {}
    sanitized = {}
    for k, v in meta.items():
        if k in ("image_base64", "raw_image", "audio_base64"):
            sanitized[k] = "[REDACTED_PAYLOAD]"
        elif isinstance(v, str) and len(v) > 20000:
            sanitized[k] = v[:200] + "...[TRUNCATED]"
        else:
            sanitized[k] = v
    return sanitized

def save_conversation_message(
    conversation_id: str,
    sender: str,
    text: str,
    intent: str = "general",
    feature: str = "assistant",
    metadata: Optional[Dict[str, Any]] = None,
    language: str = "te",
    owner_id: Optional[str] = "guest",
) -> str:
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        cursor.execute("SELECT id, owner_session_id FROM conversations WHERE id = ?", (conversation_id,))
        existing = cursor.fetchone()
        if not existing:
            if not owner_id:
                raise ValueError("A server session is required to create a conversation")
            cursor.execute(
                "INSERT INTO conversations (id, user_id, owner_session_id, language, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, owner_id, owner_id, language, now_iso(), now_iso()),
            )
        else:
            if not owner_id or existing["owner_session_id"] != owner_id:
                raise PermissionError("Conversation does not belong to this session")
            cursor.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now_iso(), conversation_id))

        msg_id = f"msg_{uuid.uuid4().hex}"
        meta_str = json.dumps(_sanitize_metadata(metadata))
        cursor.execute(
            "INSERT INTO messages (id, conversation_id, sender, text, intent, feature, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, sender, text, intent, feature, meta_str, now_iso()),
        )
        conn.commit()
        return msg_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_conversation_history(conversation_id: str, limit: int = 50, offset: int = 0, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
    bounded_limit = max(1, min(100, limit))
    bounded_offset = max(0, offset)
    conn = get_db_connection()
    cursor = conn.cursor()
    if owner_id is None:
        cursor.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?", (conversation_id, bounded_limit, bounded_offset))
    else:
        cursor.execute(
            "SELECT m.* FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE m.conversation_id = ? AND c.owner_session_id = ? ORDER BY m.created_at ASC LIMIT ? OFFSET ?",
            (conversation_id, owner_id, bounded_limit, bounded_offset)
        )
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            d["metadata"] = {}
        result.append(d)
    return result

def conversation_exists(conversation_id: str) -> bool:
    conn = get_db_connection()
    row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    conn.close()
    return row is not None


def conversation_belongs_to_user(conversation_id: str, owner_id: str) -> bool:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT 1 FROM conversations WHERE id = ? AND owner_session_id = ?",
        (conversation_id, owner_id),
    ).fetchone()
    conn.close()
    return row is not None


def clear_conversation_history(conversation_id: str, owner_id: Optional[str] = None):
    conn = get_db_connection()
    with conn:
        if owner_id is not None:
            row = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND owner_session_id = ?",
                (conversation_id, owner_id),
            ).fetchone()
            if not row:
                raise PermissionError("Conversation does not belong to this session")
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversation_sessions WHERE conversation_id = ?", (conversation_id,))
        if owner_id is None:
            # Legacy/internal clear: remove the conversation record entirely.
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        # For an authenticated browser session, retain the conversation's
        # ownership record so subsequent history requests return an empty list.
    conn.close()

def get_conversation_session(conversation_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversation_sessions WHERE conversation_id = ?", (conversation_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d["collected_slots"] = json.loads(d.get("collected_slots_json") or "{}")
        except Exception:
            d["collected_slots"] = {}
        try:
            d["missing_slots"] = json.loads(d.get("missing_slots_json") or "[]")
        except Exception:
            d["missing_slots"] = []
        return d
    return {
        "conversation_id": conversation_id,
        "pending_workflow": None,
        "collected_slots": {},
        "missing_slots": [],
    }

def save_conversation_session(
    conversation_id: str,
    pending_workflow: Optional[str],
    collected_slots: Optional[Dict[str, Any]] = None,
    missing_slots: Optional[List[str]] = None
):
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT conversation_id FROM conversation_sessions WHERE conversation_id = ?", (conversation_id,))
        slots_str = json.dumps(collected_slots or {})
        missing_str = json.dumps(missing_slots or [])
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO conversation_sessions (conversation_id, pending_workflow, collected_slots_json, missing_slots_json, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, pending_workflow, slots_str, missing_str, now_iso())
            )
        else:
            cursor.execute(
                "UPDATE conversation_sessions SET pending_workflow = ?, collected_slots_json = ?, missing_slots_json = ?, updated_at = ? WHERE conversation_id = ?",
                (pending_workflow, slots_str, missing_str, now_iso(), conversation_id)
            )
    conn.close()

def clear_conversation_session(conversation_id: str):
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM conversation_sessions WHERE conversation_id = ?", (conversation_id,))
    conn.close()

def check_database_health() -> bool:
    """Verifies SQLite connection and query execution."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0] == 1)
    except Exception:
        return False

def check_storage_writable() -> bool:
    """Verifies that the database storage path directory is writable."""
    try:
        db_dir = os.path.dirname(os.path.abspath(settings.DATABASE_PATH))
        os.makedirs(db_dir, exist_ok=True)
        # Use a unique, exclusively-created file so concurrent readiness
        # probes cannot overwrite or remove an unrelated file in this directory.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".healthcheck_write_test_",
            dir=db_dir, delete=True,
        ) as test_file:
            test_file.write("ok")
            test_file.flush()
        return True
    except Exception:
        return False


def consume_rate_limit(rate_key: str, limit: int, window_seconds: int) -> bool:
    """SQLite-backed fixed-window limiter shared by workers using the same DB."""
    now = int(datetime.now(timezone.utc).timestamp())
    window_start = now - (now % window_seconds)
    conn = get_db_connection()
    with conn:
        row = conn.execute(
            "SELECT window_started, request_count FROM api_rate_limits WHERE rate_key = ?",
            (rate_key,),
        ).fetchone()
        if not row or int(row["window_started"]) != window_start:
            conn.execute(
                "INSERT INTO api_rate_limits(rate_key, window_started, request_count) VALUES (?, ?, 1) "
                "ON CONFLICT(rate_key) DO UPDATE SET window_started=excluded.window_started, request_count=1",
                (rate_key, window_start),
            )
            allowed = True
        elif int(row["request_count"]) >= limit:
            allowed = False
        else:
            conn.execute(
                "UPDATE api_rate_limits SET request_count = request_count + 1 WHERE rate_key = ?",
                (rate_key,),
            )
            allowed = True
    conn.close()
    return allowed
