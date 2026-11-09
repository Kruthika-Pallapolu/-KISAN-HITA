from fastapi import APIRouter, Depends, Request

from ..auth import current_farmer_session
from ..models.schemas import CropHealthRequest, CropHealthResponse
from ..rate_limit import enforce_rate_limit
from ..services.crop_health_service import CropHealthService

router = APIRouter(prefix="/api/crop-health", tags=["crop_health"])


@router.post("/diagnose", response_model=CropHealthResponse)
async def diagnose_crop_health(
    req: CropHealthRequest,
    request: Request,
    owner_id: str = Depends(current_farmer_session),
):
    enforce_rate_limit(request, "crop-health", 8, 60, owner_id)
    enforce_rate_limit(request, "crop-health-ip", 30, 60)
    if req.image_base64:
        enforce_rate_limit(None, "crop-health-image", 4, 60, owner_id)
        enforce_rate_limit(request, "crop-health-image-ip", 12, 60)
    return await CropHealthService.evaluate_crop_health_async(
        crop_name=req.crop_name,
        symptoms=req.symptoms,
        onset_days=req.onset_days,
        affected_spread=req.affected_spread,
        image_base64=req.image_base64,
        language=req.language,
    )
