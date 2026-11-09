from fastapi import APIRouter, Depends
from ..auth import current_farmer_session
from ..models.schemas import CropAdvisorRequest, CropAdvisorResponse
from ..services.crop_service import CropAdvisorService

router = APIRouter(prefix="/api/crop-advisor", tags=["crop_advisor"])

@router.post("/recommend", response_model=CropAdvisorResponse)
async def get_crop_recommendations(req: CropAdvisorRequest, account_id: str = Depends(current_farmer_session)):
    return CropAdvisorService.get_recommendations(
        soil=req.soil_type,
        water=req.water_availability,
        season=req.growing_season,
        district=req.district,
        state=req.state
    )

