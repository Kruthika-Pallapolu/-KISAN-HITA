import re
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import current_farmer_session
from ..database import (
    save_conversation_message,
    get_conversation_history,
    clear_conversation_history,
    get_conversation_session,
    conversation_belongs_to_user,
)
from ..models.schemas import ChatRequest, ChatResponse
from ..rate_limit import enforce_rate_limit
from ..services.intent_router import AssistantOrchestrator

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


def resolve_conversation_id(conv_id: str | None) -> str:
    raw = (conv_id or "").strip()
    if not raw or raw in ("conv_default", "default", "null", "conv_session"):
        return f"conv_{uuid.uuid4().hex}"
    if len(raw) > 64 or not re.fullmatch(r"[a-zA-Z0-9_-]+", raw):
        raise HTTPException(status_code=400, detail="Invalid conversation identifier")
    return raw


def _ensure_owned_or_new(conversation_id: str, owner_id: str) -> None:
    # An existing identifier owned by another session must never be reused.
    from ..database import conversation_exists
    if conversation_exists(conversation_id) and not conversation_belongs_to_user(conversation_id, owner_id):
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    http_request: Request,
    owner_id: str = Depends(current_farmer_session),
):
    conversation_id = resolve_conversation_id(request.conversation_id)
    # The browser can retain a local conversation ID after its server-issued
    # session cookie expires or is cleared. Never read that other session's
    # history; rotate to a fresh ID and process this request as a new chat.
    # This makes stale browser state recover without leaking conversation data.
    from ..database import conversation_exists
    if conversation_exists(conversation_id) and not conversation_belongs_to_user(conversation_id, owner_id):
        logger.info("Rotating stale assistant conversation ID for a new browser session")
        conversation_id = f"conv_{uuid.uuid4().hex}"
    enforce_rate_limit(None, "assistant-chat", 20, 60, owner_id)  # keyed by server session
    enforce_rate_limit(http_request, "assistant-chat-ip", 60, 60)
    if request.image_base64:
        enforce_rate_limit(None, "assistant-image", 4, 60, owner_id)
        enforce_rate_limit(http_request, "assistant-image-ip", 12, 60)
    try:
        history = get_conversation_history(conversation_id, owner_id=owner_id)
        save_conversation_message(
            conversation_id=conversation_id,
            sender="user",
            text=request.message,
            language=request.language,
            owner_id=owner_id,
        )
        response = await AssistantOrchestrator.process_user_query(
            message=request.message,
            conversation_id=conversation_id,
            language=request.language,
            farm_context=request.farm_context,
            conversation_history=history,
            image_base64=request.image_base64,
        )
        response.conversation_id = conversation_id
        save_conversation_message(
            conversation_id=conversation_id,
            sender="assistant",
            text=response.reply_text,
            intent=response.intent,
            feature=response.routed_feature or "assistant",
            metadata=response.feature_data,
            language=request.language,
            owner_id=owner_id,
        )
        return response
    except PermissionError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled assistant chat failure (conversation_id=%s)", conversation_id)
        raise HTTPException(status_code=500, detail="Assistant failed to process query.")


@router.get("/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
    owner_id: str = Depends(current_farmer_session),
):
    valid_id = resolve_conversation_id(conversation_id)
    if not conversation_belongs_to_user(valid_id, owner_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return get_conversation_history(valid_id, limit=limit, offset=offset, owner_id=owner_id)


@router.get("/session/{conversation_id}")
async def get_session(conversation_id: str, owner_id: str = Depends(current_farmer_session)):
    valid_id = resolve_conversation_id(conversation_id)
    if not conversation_belongs_to_user(valid_id, owner_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return get_conversation_session(valid_id)


@router.post("/clear/{conversation_id}")
async def clear_history(conversation_id: str, owner_id: str = Depends(current_farmer_session)):
    valid_id = resolve_conversation_id(conversation_id)
    try:
        clear_conversation_history(valid_id, owner_id)
    except PermissionError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "cleared", "conversation_id": valid_id}
