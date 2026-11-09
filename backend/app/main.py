from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db, check_database_health, check_storage_writable
from .services.gemini_service import GeminiAIService
from .routers import (
    assistant,
    weather,
    crop_advisor,
    crop_health,
    market_prices,
    voice,
    settings as settings_router,
    authentication,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One reusable connection pool for outbound Timbre requests.
    app.state.gnani_tts_client = httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=5.0),
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=30.0,
        ),
    )

    try:
        init_db()
        yield
    finally:
        await app.state.gnani_tts_client.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Voice-first AI agricultural assistant for Indian farmers",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"],
)

# Include all module routers
app.include_router(assistant.router)
app.include_router(weather.router)
app.include_router(crop_advisor.router)
app.include_router(crop_health.router)
app.include_router(market_prices.router)
app.include_router(voice.router)
app.include_router(settings_router.router)
app.include_router(authentication.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "gnani_live_enabled": settings.GNANI_LIVE_ENABLED,
    }


@app.get("/api/ready")
def readiness_check(response: Response):
    """
    Readiness probe for cloud orchestrators.
    Verifies database connectivity, storage writability, and configuration.
    """
    db_ok = check_database_health()
    storage_ok = check_storage_writable()
    gemini_ready = GeminiAIService.is_configured()
    is_ready = db_ok and storage_ok

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "storage": "writable" if storage_ok else "read_only_or_error",
        "gemini_configured": gemini_ready,
        "gnani_live_enabled": settings.GNANI_LIVE_ENABLED,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# Serve the production React frontend from the same Render service.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
