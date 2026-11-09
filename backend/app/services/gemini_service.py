import asyncio
import base64
import binascii
import io
import logging
import time
import warnings
from typing import Optional, Dict, Any, List
from ..config import settings
from .crop_health_localization import AI_VISION_PREFIXES, AI_VISION_MESSAGES, SUPPORTED_LANGUAGES
from .image_validator import ImageValidator, ImageValidationError
from .assistant_instructions import LANGUAGE_NAMES, build_assistant_instruction

logger = logging.getLogger("gemini_service")

# Filter benign AFC notices in google.genai SDK
warnings.filterwarnings("ignore", message=".*automatic function calling.*")

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# Concurrency limiter to protect API quota from accidental exhaustion
_GEMINI_SEMAPHORE = asyncio.Semaphore(5)
DEFAULT_TIMEOUT_SECONDS = 12.0


def _create_gemini_client():
    # The SDK-level timeout bounds the worker thread even when asyncio.wait_for
    # cancels the awaiting coroutine.
    http_options = types.HttpOptions(timeout=int(DEFAULT_TIMEOUT_SECONDS * 1000))
    return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=http_options)


class GeminiAIService:
    @staticmethod
    def is_configured() -> bool:
        """Returns True only when SDK is installed, key is present, and Gemini is enabled."""
        return bool(settings.GEMINI_API_KEY and settings.GEMINI_ENABLED and genai is not None)

    @staticmethod
    def get_connection_status() -> Dict[str, Any]:
        """
        Returns safe configuration status of the Google AI/Gemini integration.
        Never exposes the API key or partial key characters publicly.
        """
        is_sdk_available = genai is not None
        has_key = bool(settings.GEMINI_API_KEY)
        
        status = "not_configured"
        message = "Google Gemini API key is not configured. Assistant is operating with the local agricultural engine."
        
        if not is_sdk_available:
            status = "sdk_missing"
            message = "Google GenAI SDK is not installed in the Python environment."
        elif has_key and settings.GEMINI_ENABLED:
            status = "configured"
            message = f"Gemini API configured for model {settings.GEMINI_MODEL}."
        elif has_key and not settings.GEMINI_ENABLED:
            status = "disabled"
            message = "Gemini integration is disabled in configuration."
            
        return {
            "status": status,
            "provider": "Google GenAI (Gemini)",
            "sdk_available": is_sdk_available,
            "key_configured": has_key,
            "model": settings.GEMINI_MODEL,
            "enabled": settings.GEMINI_ENABLED,
            "message": message
        }

    @staticmethod
    async def test_connection() -> Dict[str, Any]:
        """
        Tests outbound connection to Google AI (Gemini) using the server's configured environment key.
        Does NOT accept arbitrary client-supplied keys to prevent probing or quota drain.
        """
        target_model = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
        
        if not settings.GEMINI_API_KEY:
            return {
                "status": "not_configured",
                "provider": "Google GenAI SDK",
                "model": target_model,
                "message": "GEMINI_API_KEY is not configured in backend environment.",
                "latency_ms": 0
            }
            
        if not genai:
            return {
                "status": "error",
                "provider": "Google GenAI SDK",
                "model": target_model,
                "message": "google.genai SDK is not installed.",
                "latency_ms": 0
            }
            
        t0 = time.time()
        try:
            client = _create_gemini_client()
            
            def _sync_ping():
                return client.models.generate_content(
                    model=target_model,
                    contents="Respond with only the single word: READY",
                    config=types.GenerateContentConfig(
                        max_output_tokens=64
                    )
                )

            async with _GEMINI_SEMAPHORE:
                res = await asyncio.wait_for(
                    asyncio.to_thread(_sync_ping),
                    timeout=DEFAULT_TIMEOUT_SECONDS
                )

            latency = round((time.time() - t0) * 1000, 2)
            if res and res.text:
                return {
                    "status": "success",
                    "provider": "Google GenAI (Gemini)",
                    "model": target_model,
                    "message": "Connection verified successfully.",
                    "latency_ms": latency
                }
            else:
                return {
                    "status": "error",
                    "provider": "Google GenAI (Gemini)",
                    "model": target_model,
                    "message": "Empty response received from Gemini endpoint.",
                    "latency_ms": latency
                }
        except asyncio.TimeoutError:
            latency = round((time.time() - t0) * 1000, 2)
            logger.warning("Gemini connection test timed out.")
            return {
                "status": "timeout",
                "provider": "Google GenAI (Gemini)",
                "model": target_model,
                "message": f"Connection test timed out after {DEFAULT_TIMEOUT_SECONDS}s.",
                "latency_ms": latency
            }
        except Exception as exc:
            latency = round((time.time() - t0) * 1000, 2)
            logger.warning(f"Gemini connection test failed: {exc.__class__.__name__}")
            return {
                "status": "error",
                "provider": "Google GenAI (Gemini)",
                "model": target_model,
                "message": f"Connection test encountered: {exc.__class__.__name__}",
                "latency_ms": latency
            }

    @staticmethod
    async def generate_agricultural_response(
        query: str,
        language: str = "en",
        farm_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Generates an authentic, evidence-backed agricultural response using Google Gemini.
        Runs asynchronously via worker thread to avoid blocking the FastAPI event loop.
        Never assumes unconfirmed farmer locations or soil types.
        Safeguarded against prompt injection via delimited query context.
        """
        if not GeminiAIService.is_configured():
            return None

        # Context instructions are centralized and never supply defaults for missing farm facts.
        system_instruction = build_assistant_instruction(language, farm_context)

        try:
            client = _create_gemini_client()
            
            # Format conversational history for context continuity
            formatted_contents = []
            if conversation_history:
                for msg in conversation_history[-6:]:
                    role = "user" if msg.get("sender") == "user" else "model"
                    formatted_contents.append(f"{role.upper()}: {msg.get('text', '')}")
                    
            # Safely delimit untrusted user query
            formatted_contents.append(f"<farmer_query>\n{query}\n</farmer_query>")
            full_prompt = "\n\n".join(formatted_contents)

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=2048
            )

            def _sync_generate():
                return client.models.generate_content(
                    model=settings.GEMINI_MODEL or "gemini-3.1-flash-lite",
                    contents=full_prompt,
                    config=config
                )

            async with _GEMINI_SEMAPHORE:
                res = await asyncio.wait_for(
                    asyncio.to_thread(_sync_generate),
                    timeout=DEFAULT_TIMEOUT_SECONDS
                )

            if res and res.text:
                return res.text.strip()
        except asyncio.TimeoutError:
            logger.warning("Gemini agricultural response generation timed out.")
            return None
        except Exception as exc:
            logger.warning(f"Gemini agricultural response generation failed: {exc.__class__.__name__}")
            return None

        return None

    @staticmethod
    async def analyze_crop_image(
        image_base64: Optional[str] = None,
        crop_name: str = "Crop",
        symptoms: str = "",
        language: str = "en",
        image_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini Vision to inspect the crop photograph for symptoms, discoloration, and stress.
        Runs asynchronously via worker thread to avoid blocking the event loop.
        - Validates and verifies raw image bytes.
        - Uses verified MIME type (JPEG/PNG/WebP).
        - Clearly marks visual observations as preliminary AI observations (not a confirmed diagnosis).
        - Never prescribes chemical pesticides or dosages.
        - Handles timeouts and failures gracefully without inventing fake observations.
        - Never logs raw bytes or base64 strings.
        """
        lang = language[:2].lower() if language else "en"
        if lang not in SUPPORTED_LANGUAGES:
            lang = "en"

        # Check if Gemini is configured & enabled
        if not GeminiAIService.is_configured():
            return {
                "visual_observations": None,
                "status": "unavailable",
                "message": AI_VISION_MESSAGES["unavailable"].get(lang, AI_VISION_MESSAGES["unavailable"]["en"])
            }

        # Acquire validated bytes & MIME
        if image_bytes and mime_type:
            raw_bytes = image_bytes
            verified_mime = mime_type
        elif image_base64:
            try:
                raw_bytes, verified_mime = ImageValidator.validate_crop_image(image_base64, language=lang)
            except ImageValidationError as exc:
                return {
                    "visual_observations": None,
                    "status": "error",
                    "error": exc.message
                }
        else:
            return None

        lang_name = LANGUAGE_NAMES.get(lang, "Indian English")
        prompt = (
            f"You are Kisan Hita's AI Agricultural Vision Assistant examining a crop photograph for {crop_name}.\n"
            f"Farmer's reported symptoms: '{symptoms}'.\n\n"
            f"Please provide an objective, cautious visual appraisal in {lang_name}:\n"
            f"1. Visible observations: Describe only what can genuinely be seen on the leaf, stem, or plant foliage "
            f"(e.g., leaf discoloration pattern, chlorosis between veins, browning at leaf margins, circular spots, curling, or insect traces).\n"
            f"2. Potential stress indicators: Mention whether the visual signs are consistent with moisture imbalance, physical abrasion/weather stress, or foliar blemishes.\n"
            f"3. What to verify physically: What the farmer should check by hand (e.g. check leaf undersides for tiny pests with a lens, inspect soil moisture around root depth, observe whether upper new leaves look healthy).\n\n"
            f"STRICT DOMAIN CONSTRAINTS:\n"
            f"- State clearly that these are preliminary AI visual observations, NOT a confirmed laboratory diagnosis.\n"
            f"- NEVER prescribe synthetic chemical pesticide names, dosages, or chemical tank mixtures.\n"
            f"- NEVER invent disease confidence scores or percentages (e.g. do not say '95% confident').\n"
            f"- Use natural, respectful everyday farmer language in {lang_name}."
        )

        model_name = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
        try:
            client = _create_gemini_client()
            part = types.Part.from_bytes(data=raw_bytes, mime_type=verified_mime)

            config = types.GenerateContentConfig(
                max_output_tokens=1536
            )

            def _sync_vision():
                return client.models.generate_content(
                    model=model_name,
                    contents=[part, prompt],
                    config=config
                )

            async with _GEMINI_SEMAPHORE:
                res = await asyncio.wait_for(
                    asyncio.to_thread(_sync_vision),
                    timeout=DEFAULT_TIMEOUT_SECONDS
                )

            if res and res.text and res.text.strip():
                prefix = AI_VISION_PREFIXES.get(lang, AI_VISION_PREFIXES["en"])
                return {
                    "visual_observations": f"{prefix}\n{res.text.strip()}",
                    "status": "completed",
                    "model": model_name
                }
            else:
                return {
                    "visual_observations": None,
                    "status": "unavailable",
                    "message": AI_VISION_MESSAGES["unavailable"].get(lang, AI_VISION_MESSAGES["unavailable"]["en"])
                }
        except asyncio.TimeoutError:
            logger.warning("Gemini Vision appraisal timed out.")
            err_msg = AI_VISION_MESSAGES["error"].get(lang, AI_VISION_MESSAGES["error"]["en"])
            return {
                "visual_observations": None,
                "status": "error",
                "error": err_msg
            }
        except Exception as exc:
            logger.warning(f"Gemini Vision appraisal encountered an issue: {exc.__class__.__name__}")
            err_msg = AI_VISION_MESSAGES["error"].get(lang, AI_VISION_MESSAGES["error"]["en"])
            return {
                "visual_observations": None,
                "status": "error",
                "error": err_msg
            }
