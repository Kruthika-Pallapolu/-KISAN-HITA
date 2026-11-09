"""
Kisan Hita — Check My Crop Agronomic Service
Provides evidence-conscious, safety-first crop health appraisals:
- Strictly separates:
  1. Farmer-reported symptoms
  2. AI-generated visual observations (preliminary, unconfirmed)
  3. Possible contributing factors (plausible agronomic possibilities, not diagnoses)
  4. Expert-confirmed diagnosis note (never claimed by Kisan Hita)
- Removes unsupported disease guesses (no Fusarium/Rhizoctonia/nematodes).
- No automatic nitrogen deficiency claims for yellowing.
- No automatic fungal claims for spots.
- Enforces strict image validation (JPEG/PNG/WebP, 10MB limit).
- True multilingual responses across Telugu, English, Hindi, Tamil, Kannada, Malayalam, Marathi.
- Recommends KVK and toll-free Kisan Call Centre (1800-180-1551).
"""

import logging
from typing import List, Optional
from ..models.schemas import CropHealthResponse
from .crop_health_localization import (
    SUPPORTED_LANGUAGES,
    SYMPTOM_KNOWLEDGE_BASE,
    SAFETY_NOTICES,
    DIAGNOSTIC_DISCLAIMERS,
    EXPERT_CONFIRMATION_NOTES,
    EXTENSION_CONTACTS,
    AI_VISION_MESSAGES,
    detect_symptom_group,
    get_farmer_reported_summary,
    get_cautious_assessment_text,
)
from .image_validator import ImageValidator, ImageValidationError
from .gemini_service import GeminiAIService

logger = logging.getLogger("crop_health_service")

class CropHealthService:
    @staticmethod
    def evaluate_crop_health(
        crop_name: str,
        symptoms: str,
        onset_days: Optional[str] = None,
        affected_spread: Optional[str] = None,
        image_base64: Optional[str] = None,
        language: str = "en"
    ) -> CropHealthResponse:
        """
        Generates an agronomic evaluation cleanly distinguishing farmer-reported
        symptoms, plausible contributing factors, non-chemical cultural steps,
        and expert confirmation requirements across all 7 languages.
        """
        c_clean = crop_name.strip()
        sym_clean = symptoms.strip()
        lang = language[:2].lower() if language else "en"
        if lang not in SUPPORTED_LANGUAGES:
            lang = "en"

        has_img = bool(image_base64 and len(image_base64.strip()) > 10)

        # Detect cautious symptom category
        group = detect_symptom_group(sym_clean)
        kb_entry = SYMPTOM_KNOWLEDGE_BASE.get(group, SYMPTOM_KNOWLEDGE_BASE["general"])

        factors = kb_entry["factors"].get(lang, kb_entry["factors"]["en"])
        management = kb_entry["management"].get(lang, kb_entry["management"]["en"])

        farmer_summary = get_farmer_reported_summary(
            language=lang,
            crop_name=c_clean,
            symptoms=sym_clean,
            onset_days=onset_days,
            affected_spread=affected_spread
        )

        assessment = get_cautious_assessment_text(
            language=lang,
            crop_name=c_clean,
            symptoms=sym_clean,
            onset_days=onset_days,
            affected_spread=affected_spread
        )

        safety_notice = SAFETY_NOTICES.get(lang, SAFETY_NOTICES["en"])
        diagnostic_disclaimer = DIAGNOSTIC_DISCLAIMERS.get(lang, DIAGNOSTIC_DISCLAIMERS["en"])
        expert_confirmation_note = EXPERT_CONFIRMATION_NOTES.get(lang, EXPERT_CONFIRMATION_NOTES["en"])
        extension_contact = EXTENSION_CONTACTS.get(lang, EXTENSION_CONTACTS["en"])

        return CropHealthResponse(
            crop_name=c_clean,
            reported_symptoms=sym_clean,
            cautious_assessment=assessment,
            potential_factors=factors,
            cultural_management_steps=management,
            safety_notice=safety_notice,
            extension_contact=extension_contact,
            has_image=has_img,
            diagnostic_disclaimer=diagnostic_disclaimer,
            ai_observations=None,
            farmer_reported_summary=farmer_summary,
            visual_analysis_status="not_provided" if not has_img else "unavailable",
            expert_confirmation_note=expert_confirmation_note
        )

    @staticmethod
    async def evaluate_crop_health_async(
        crop_name: str,
        symptoms: str,
        onset_days: Optional[str] = None,
        affected_spread: Optional[str] = None,
        image_base64: Optional[str] = None,
        language: str = "en"
    ) -> CropHealthResponse:
        """
        Async evaluation including verified Gemini Vision appraisal.
        - Validates image bytes securely.
        - Invokes Gemini Vision with agronomic constraints.
        - Correctly sets visual_analysis_status ('completed' | 'unavailable' | 'error' | 'not_provided').
        """
        lang = language[:2].lower() if language else "en"
        if lang not in SUPPORTED_LANGUAGES:
            lang = "en"

        base_resp = CropHealthService.evaluate_crop_health(
            crop_name=crop_name,
            symptoms=symptoms,
            onset_days=onset_days,
            affected_spread=affected_spread,
            image_base64=image_base64,
            language=lang
        )

        # If no image was provided, status is cleanly not_provided
        if not image_base64 or not image_base64.strip():
            base_resp.has_image = False
            base_resp.visual_analysis_status = "not_provided"
            base_resp.ai_observations = None
            return base_resp

        base_resp.has_image = True

        # Validate image payload
        try:
            raw_bytes, verified_mime = ImageValidator.validate_crop_image(image_base64, language=lang)
        except ImageValidationError as exc:
            logger.warning(f"Image validation rejected upload: {exc.error_type}")
            raise

        # Check if Gemini AI Vision is configured
        if not GeminiAIService.is_configured():
            logger.info("Gemini Vision is unconfigured or disabled.")
            base_resp.visual_analysis_status = "unavailable"
            base_resp.ai_observations = None
            return base_resp

        # Execute Gemini Vision inspection with validated bytes
        try:
            ai_vision = await GeminiAIService.analyze_crop_image(
                image_bytes=raw_bytes,
                mime_type=verified_mime,
                crop_name=crop_name,
                symptoms=symptoms,
                language=lang
            )
        except Exception:
            logger.exception("Gemini Vision analysis failed")
            base_resp.visual_analysis_status = "error"
            base_resp.ai_observations = None
            return base_resp

        if ai_vision and ai_vision.get("status") == "unavailable":
            base_resp.visual_analysis_status = "unavailable"
            base_resp.ai_observations = ai_vision.get("message")
        elif ai_vision and ai_vision.get("status") == "error":
            base_resp.visual_analysis_status = "error"
            base_resp.ai_observations = ai_vision.get("error") or ai_vision.get("message")
        elif ai_vision and ai_vision.get("visual_observations"):
            base_resp.ai_observations = ai_vision.get("visual_observations")
            base_resp.visual_analysis_status = "completed"
        else:
            logger.info("Gemini Vision returned no observations.")
            base_resp.visual_analysis_status = "error"
            base_resp.ai_observations = None

        return base_resp
