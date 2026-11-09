from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Optional
from ..auth import current_farmer_session
from ..models.schemas import MarketPriceResponse, MarketPriceRequest, normalize_language_code
from ..services.market_service import MarketPriceService, KNOWN_COMMODITIES
from ..services.market_provider import MarketProviderError

router = APIRouter(prefix="/api/market-prices", tags=["market_prices"])

@router.get("/search", response_model=MarketPriceResponse)
async def search_market_prices(
    commodity: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    mandi: Optional[str] = Query(None),
    variety: Optional[str] = Query(None),
    language: str = Query("en", min_length=2, max_length=5),
    account_id: str = Depends(current_farmer_session),
):
    try:
        language = normalize_language_code(language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    try:
        return await MarketPriceService.get_market_prices(
            commodity=commodity,
            state=state,
            district=district,
            mandi=mandi,
            variety=variety,
            language=language
        )
    except MarketProviderError as exc:
        raise HTTPException(status_code=exc.http_status, detail={"code": exc.code, "message": exc.message}) from None

@router.post("/search", response_model=MarketPriceResponse)
async def search_market_prices_post(req: MarketPriceRequest, account_id: str = Depends(current_farmer_session)):
    try:
        return await MarketPriceService.get_market_prices(
            commodity=req.commodity,
            state=req.state,
            district=req.district,
            mandi=req.mandi,
            variety=req.variety,
            language=req.language
        )
    except MarketProviderError as exc:
        raise HTTPException(status_code=exc.http_status, detail={"code": exc.code, "message": exc.message}) from None

@router.get("/commodities")
async def list_commodities(account_id: str = Depends(current_farmer_session)):
    commodities = KNOWN_COMMODITIES
    return {
        "commodities": commodities,
        "mandis": [],
        "districts": [],
        "states": []
    }

