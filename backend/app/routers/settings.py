from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import current_session
from ..config import settings
from ..database import get_user_profile, update_user_profile
from ..models.schemas import UserProfileUpdate
from ..rate_limit import enforce_rate_limit
from ..services.gemini_service import GeminiAIService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/profile")
async def get_profile(owner_id: str = Depends(current_session)):
    return get_user_profile(owner_id)


@router.post("/profile")
async def update_profile(
    updates: UserProfileUpdate,
    owner_id: str = Depends(current_session),
):
    return update_user_profile(owner_id, updates.model_dump(exclude_unset=True))


@router.get("/ai-config")
async def get_ai_config():
    """Returns configuration status only; never exposes credentials."""
    return GeminiAIService.get_connection_status()


@router.post("/ai-config")
async def update_ai_config():
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Dynamic Gemini key modification is disabled; configure credentials through backend environment variables.",
    )


@router.post("/test-ai")
async def test_ai_connection(request: Request, account_id: str = Depends(current_session)):
    # This diagnostic can invoke a paid provider and is not a farmer-facing feature.
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    enforce_rate_limit(request, "gemini-connection-test", 2, 60)
    return await GeminiAIService.test_connection()
