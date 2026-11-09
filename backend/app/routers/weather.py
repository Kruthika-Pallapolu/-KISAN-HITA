import json
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException, status, Depends, Request
from typing import Optional, List
from ..auth import current_farmer_session
from ..models.schemas import WeatherData, WeatherCurrentRequest, WeatherCoordinatesRequest, normalize_language_code
from ..services.weather_service import (
    WeatherService, WeatherCoverageUnavailable, WeatherGeocodingUnavailable,
    WeatherProviderUnavailable, WeatherConfigurationMissing,
)
from ..rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/weather", tags=["weather"])

_GEO_DIRECTORY_PATH = Path(__file__).resolve().parents[3] / "frontend" / "src" / "data" / "indiaAdminLgd.json"
with _GEO_DIRECTORY_PATH.open(encoding="utf-8") as _directory_file:
    _GEO_DIRECTORY = json.load(_directory_file)
_STATE_NAMES = {state["code"]: state["name"] for state in _GEO_DIRECTORY["states"]}

@router.get("/current", response_model=WeatherData)
async def get_current_weather(
    request: Request,
    district: str = Query(..., description="District name (required)"),
    state: Optional[str] = Query(None, description="State name"),
    language: str = Query("en", min_length=2, max_length=5, description="Language code"),
    account_id: str = Depends(current_farmer_session),
):
    try:
        enforce_rate_limit(None, "weather-session", 20, 60, account_id)
        enforce_rate_limit(request, "weather-district-ip", 60, 60)
        language = normalize_language_code(language)
        return await WeatherService.get_district_weather(district, state, language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except WeatherCoverageUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_coverage_unavailable", "message": str(exc)})
    except WeatherGeocodingUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_geocoding_unavailable", "message": str(exc)})
    except WeatherConfigurationMissing as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_configuration_missing", "message": str(exc)})
    except (WeatherProviderUnavailable, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_provider_unavailable", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Weather lookup failed.")

@router.post("/current/coordinates", response_model=WeatherData)
async def get_current_weather_by_coordinates(
    req: WeatherCoordinatesRequest,
    request: Request,
    account_id: str = Depends(current_farmer_session),
):
    try:
        enforce_rate_limit(None, "weather-session", 20, 60, account_id)
        enforce_rate_limit(request, "weather-coordinate-ip", 20, 60)
        return await WeatherService.get_coordinate_weather(req.latitude, req.longitude, req.language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except WeatherCoverageUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_coverage_unavailable", "message": str(exc)})
    except WeatherGeocodingUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_geocoding_unavailable", "message": str(exc)})
    except WeatherConfigurationMissing as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_configuration_missing", "message": str(exc)})
    except (WeatherProviderUnavailable, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_provider_unavailable", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Weather lookup failed.")

@router.post("/current", response_model=WeatherData)
async def get_current_weather_post(req: WeatherCurrentRequest, request: Request, account_id: str = Depends(current_farmer_session)):
    try:
        enforce_rate_limit(None, "weather-session", 20, 60, account_id)
        enforce_rate_limit(request, "weather-district-ip", 60, 60)
        return await WeatherService.get_district_weather(req.district, req.state, req.language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except WeatherCoverageUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_coverage_unavailable", "message": str(exc)})
    except WeatherGeocodingUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_geocoding_unavailable", "message": str(exc)})
    except WeatherConfigurationMissing as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_configuration_missing", "message": str(exc)})
    except (WeatherProviderUnavailable, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "weather_provider_unavailable", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Weather lookup failed.")

@router.get("/districts")
async def get_districts(account_id: str = Depends(current_farmer_session)):
    return [
        {"key": district["id"], "name": district["name"], "state": _STATE_NAMES[district["stateCode"]]}
        for district in _GEO_DIRECTORY["districts"]
        if district["stateCode"] in _STATE_NAMES
    ]
