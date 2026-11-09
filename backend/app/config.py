import os
from dotenv import load_dotenv
from pydantic import BaseModel

# Exact development LAN origins used by phones. Keep prior addresses during
# DHCP changes so existing sessions/devices are not unexpectedly blocked.
# These are narrow entries; no wildcard origins are permitted.
MOBILE_DEV_ORIGINS = (
    "http://192.168.29.3:5173",
    "http://192.168.29.52:5173",
)

# Automatically load .env from project root if present
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))
load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = "Kisan Hita"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "kisan_hita.db")
    
    # CORS SETTINGS: Explicit production frontend origins
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    )
    
    # VOICE PROVIDER SELECTION
    VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "temporary")
    
    # GNANI AI CREDENTIAL PROTECTION
    # Strictly False during development to protect user credits (~5,000 balance).
    # Gnani integration remains dormant until explicit authorization.
    GNANI_LIVE_ENABLED: bool = os.getenv("GNANI_LIVE_ENABLED", "false").lower() == "true"
    # Modality switches are independent but cannot override the global master switch.
    GNANI_PRISMA_ENABLED: bool = os.getenv("GNANI_PRISMA_ENABLED", "false").lower() == "true"
    GNANI_TIMBRE_ENABLED: bool = os.getenv("GNANI_TIMBRE_ENABLED", "false").lower() == "true"
    GNANI_API_KEY: str = os.getenv("GNANI_API_KEY", "")
    GNANI_TOKEN: str = os.getenv("GNANI_TOKEN", "")
    GNANI_PRISMA_MODEL: str = os.getenv("GNANI_PRISMA_MODEL", "prisma-v3.0")
    GNANI_TIMBRE_MODEL: str = os.getenv("GNANI_TIMBRE_MODEL", "timbre-v3.0")
    GNANI_TIMBRE_VOICE_EN: str = os.getenv("GNANI_TIMBRE_VOICE_EN", "")
    GNANI_TIMBRE_VOICE_TE: str = os.getenv("GNANI_TIMBRE_VOICE_TE", "")
    GNANI_TIMBRE_VOICE_HI: str = os.getenv("GNANI_TIMBRE_VOICE_HI", "")
    GNANI_TIMBRE_VOICE_TA: str = os.getenv("GNANI_TIMBRE_VOICE_TA", "")
    GNANI_TIMBRE_VOICE_KN: str = os.getenv("GNANI_TIMBRE_VOICE_KN", "")
    GNANI_TIMBRE_VOICE_ML: str = os.getenv("GNANI_TIMBRE_VOICE_ML", "")
    GNANI_TIMBRE_VOICE_MR: str = os.getenv("GNANI_TIMBRE_VOICE_MR", "")
    
    # Official Gnani Vachana API endpoints (Dormant contracts)
    GNANI_STT_URL: str = os.getenv("GNANI_STT_URL", "https://api.vachana.ai/stt/v3")
    GNANI_TTS_URL: str = os.getenv("GNANI_TTS_URL", "https://api.vachana.ai/api/v1/tts/inference")
    GNANI_WS_STT_URL: str = os.getenv("GNANI_WS_STT_URL", "wss://api.vachana.ai/stt/v3/stream")
    
    # GOOGLE AI / GEMINI CONFIGURATION
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    GEMINI_ENABLED: bool = os.getenv("GEMINI_ENABLED", "true").lower() == "true"

    # Optional server-side official market feed credential. Never sent to the frontend.

    # Deterministic demo mode is used by explicitly demo-backed features such
    # as market prices. Weather always requires the live WeatherAPI provider.
    DEMO_DATA_ENABLED: bool = os.getenv("DEMO_DATA_ENABLED", "true").lower() == "true"
    
    # WeatherAPI.com credentials stay server-side under one canonical name.
    WEATHERAPI_KEY: str = os.getenv("WEATHERAPI_KEY", "")
    WEATHER_TIMEOUT_SECONDS: float = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "6.0"))
    
    # Supported languages: Telugu, English, Hindi, Tamil, Kannada, Malayalam, Marathi
    SUPPORTED_LANGUAGES: list[str] = ["te", "en", "hi", "ta", "kn", "ml", "mr"]
    DEFAULT_LANGUAGE: str = "en"

    @property
    def allowed_origins_list(self) -> list[str]:
        if not self.ALLOWED_ORIGINS:
            origins = [
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000"
            ]
        elif self.ALLOWED_ORIGINS.strip() == "*":
            # Credentialed cookies must never be combined with wildcard CORS.
            origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
        else:
            origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        for mobile_origin in MOBILE_DEV_ORIGINS:
            if mobile_origin not in origins:
                origins.append(mobile_origin)
        return origins

settings = Settings()
