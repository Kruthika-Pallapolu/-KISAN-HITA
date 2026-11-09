from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from ..services.image_validator import ImageValidator

SUPPORTED_LANG_CODES = {"te", "en", "hi", "ta", "kn", "ml", "mr"}

def normalize_language_code(v: str) -> str:
    raw = (v or "en").strip().lower().replace("_", "-")
    parts = raw.split("-")
    lang = parts[0]
    if lang not in SUPPORTED_LANG_CODES or len(parts) > 2 or (len(parts) == 2 and parts[1] != "in"):
        raise ValueError(f"Unsupported language code '{v}'. Supported: {sorted(SUPPORTED_LANG_CODES)} (or their -IN locale)")
    return lang


_validate_language = normalize_language_code

# =========================================================================
# Chat / Assistant Schemas
# =========================================================================
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Farmer inquiry text")
    conversation_id: Optional[str] = Field(None, max_length=64, description="Unique conversation identifier")
    language: str = Field("en", max_length=64, description="Selected language code")
    farm_context: Optional[Dict[str, Any]] = None
    image_base64: Optional[str] = None

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

    @model_validator(mode="after")
    def validate_chat_payload(self) -> "ChatRequest":
        if self.image_base64 is not None:
            # Validates format, size (<10MB raw), decoding, and PIL integrity
            ImageValidator.validate_crop_image(self.image_base64, self.language)
        return self

class ChatResponse(BaseModel):
    conversation_id: str
    reply_text: str
    language: str
    intent: str
    routed_feature: Optional[str] = None
    feature_data: Optional[Dict[str, Any]] = None
    suggested_actions: List[str] = Field(default_factory=list)
    audio_available: bool = False
    pending_workflow: Optional[str] = None
    collected_slots: Optional[Dict[str, Any]] = None
    next_slot: Optional[str] = None

# =========================================================================
# Weather Schemas
# =========================================================================
class WeatherCurrentRequest(BaseModel):
    district: str = Field(..., min_length=2, max_length=64, description="District name")
    state: Optional[str] = Field(None, max_length=64, description="State name")
    language: str = Field("en", max_length=64, description="Language code")

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

class WeatherCoordinatesRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    language: str = Field("en", max_length=64)

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

class ForecastDay(BaseModel):
    day_name: str
    date: str
    temp_max: float
    temp_min: float
    condition: str
    condition_code: Optional[int] = None
    condition_icon_url: Optional[str] = None
    precipitation_probability: int
    icon: str = "cloud-sun"

class WeatherData(BaseModel):
    district: str
    state: str
    country: Optional[str] = None
    temperature: float
    feels_like: Optional[float] = None
    condition: str
    condition_code: Optional[int] = None
    condition_icon_url: Optional[str] = None
    humidity: int
    wind_speed: float
    wind_direction: Optional[str] = None
    visibility_km: Optional[float] = None
    rain_probability: int
    rainfall_mm: Optional[float] = None
    advisory: str
    irrigation_advice: str
    spray_suitability: str
    produce_protection: str
    is_official_alert: bool = False
    source: str
    coordinate_source: Optional[str] = None
    retrieval_timestamp: Optional[str] = None
    forecast: List[ForecastDay] = Field(default_factory=list)

# =========================================================================
# Crop Advisor Schemas
# =========================================================================
class CropAdvisorRequest(BaseModel):
    soil_type: str = Field(..., min_length=2, max_length=64, description="Soil classification")
    water_availability: str = Field(..., min_length=2, max_length=64, description="Water source availability")
    growing_season: str = Field(..., min_length=2, max_length=64, description="Target crop season")
    district: Optional[str] = Field(None, max_length=64)
    state: Optional[str] = Field(None, max_length=64)
    language: str = Field("en", max_length=64)

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

class CropRecommendation(BaseModel):
    crop_name: str
    variety: str
    duration_days: str
    water_requirement: str
    soil_suitability: str
    limitations: str
    next_steps: str
    citation: str
    publication_date: Optional[str] = None
    applicable_regions: List[str] = Field(default_factory=list)
    suitability_score: Optional[str] = "High Suitability (Demo Reference)"
    suitable_season: Optional[str] = None
    cultivation_guidance: Optional[str] = None

class CropAdvisorResponse(BaseModel):
    recommendations: List[CropRecommendation] = Field(default_factory=list)
    total_found: int
    soil_type: str
    growing_season: str
    water_availability: str
    disclaimer: str

# =========================================================================
# Crop Health Schemas
# =========================================================================
class CropHealthRequest(BaseModel):
    crop_name: str = Field(..., min_length=1, max_length=64)
    symptoms: str = Field(..., min_length=1, max_length=2000)
    onset_days: Optional[str] = Field(None, max_length=64)
    affected_spread: Optional[str] = Field(None, max_length=64)
    language: str = Field("en", max_length=64)
    image_base64: Optional[str] = None

    @field_validator("crop_name")
    @classmethod
    def validate_crop_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Crop name cannot be empty.")
        return cleaned

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Symptoms description cannot be empty.")
        return cleaned

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

    @model_validator(mode="after")
    def validate_image_payload(self) -> "CropHealthRequest":
        if self.image_base64 is not None:
            cleaned = self.image_base64.strip()
            # An explicitly supplied but empty image is invalid; omission alone
            # means that the farmer chose symptom-only assessment.
            ImageValidator.validate_crop_image(cleaned, self.language)
            self.image_base64 = cleaned
        return self

class CropHealthResponse(BaseModel):
    crop_name: str
    reported_symptoms: str
    cautious_assessment: str
    potential_factors: List[str] = Field(default_factory=list)
    cultural_management_steps: List[str] = Field(default_factory=list)
    safety_notice: str
    extension_contact: str
    has_image: bool = False
    diagnostic_disclaimer: str
    ai_observations: Optional[str] = None
    farmer_reported_summary: Optional[str] = None
    visual_analysis_status: Optional[str] = "not_provided"  # not_provided | completed | unavailable | error
    expert_confirmation_note: Optional[str] = None

# =========================================================================
# Market Prices Schemas
# =========================================================================
class MarketPriceRequest(BaseModel):
    commodity: Optional[str] = Field(None, max_length=64)
    state: Optional[str] = Field(None, max_length=64)
    district: Optional[str] = Field(None, max_length=64)
    mandi: Optional[str] = Field(None, max_length=64)
    variety: Optional[str] = Field(None, max_length=64)
    language: str = Field("en", max_length=64)

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

class MandiPriceItem(BaseModel):
    commodity: str
    variety: Optional[str] = None
    grade: Optional[str] = None
    market: Optional[str] = None
    district: str
    state: str
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    min_price_per_kg: Optional[float] = None
    max_price_per_kg: Optional[float] = None
    modal_price_per_kg: Optional[float] = None
    currency: str = "INR"
    unit: str = "kg"
    reported_unit: str = "INR/kg"
    data_type: str = "illustrative"
    record_date: Optional[str] = None
    freshness: str = "undated"
    source: str
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    disclaimer: str

class MarketPriceResponse(BaseModel):
    records: List[MandiPriceItem] = Field(default_factory=list)
    total_count: int
    disclaimer: str
    last_updated: str
    data_provenance: Optional[str] = None
    is_live_api: bool = False
    data_type: str = "illustrative"
    retrieved_at: Optional[str] = None
    source_url: Optional[str] = None
    related_source_url: Optional[str] = None

# =========================================================================
# Voice Schemas
# =========================================================================
class STTRequest(BaseModel):
    audio_base64: Optional[str] = None
    language: str = Field("en", max_length=64)

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

class STTResponse(BaseModel):
    transcript: str
    language: str
    confidence: Optional[float] = None
    model: str = "temporary-local-stt"
    provider: str = "temporary_development"
    is_mock: bool = False
    processing_time_ms: Optional[float] = None

class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2000, description="Input text to synthesize (max 2000 chars)")
    language: str = Field("en", max_length=64)
    voice: Optional[str] = Field(None, max_length=64)
    speed: Optional[float] = Field(1.0, ge=0.5, le=2.0)

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        return _validate_language(v)

class TTSResponse(BaseModel):
    audio_base64: Optional[str] = None
    format: str = "audio/wav"
    language: str
    voice_name: Optional[str] = None
    model: str = "temporary-local-tts"
    provider: str = "temporary_development"
    is_mock: bool = False

# =========================================================================
# Settings Schemas
# =========================================================================
class UserProfileUpdate(BaseModel):
    selected_language: Optional[str] = Field(None, max_length=64)
    assistant_name: Optional[str] = Field(None, max_length=64)
    assistant_name_prompt_completed: Optional[bool] = None
    state: Optional[str] = Field(None, max_length=64)
    district: Optional[str] = Field(None, max_length=64)
    village: Optional[str] = Field(None, max_length=64)
    soil_type: Optional[str] = Field(None, max_length=64)
    water_source: Optional[str] = Field(None, max_length=64)

    @field_validator("selected_language")
    @classmethod
    def check_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_language(v)
        return v
