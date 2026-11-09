"""
Kisan Hita — Image Validation Module
Provides secure, evidence-conscious validation of farmer-uploaded crop photos:
- Supports JPEG, PNG, and WebP only.
- Supports both raw Base64 and data URLs.
- Validates Base64 decoding and strict size limits (10MB raw).
- Inspects actual binary magic bytes rather than trusting MIME headers.
- Uses PIL verify to prevent corrupt or truncated images from reaching Gemini.
- Never logs raw Base64 or image bytes.
"""

import base64
import binascii
import io
import logging
from typing import Tuple, Optional
from PIL import Image
from .crop_health_localization import IMAGE_ERROR_MESSAGES, SUPPORTED_LANGUAGES

logger = logging.getLogger("image_validator")

# Maximum size limits
MAX_RAW_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB raw binary limit
MAX_BASE64_LENGTH = 14 * 1024 * 1024    # ~14 MB string limit for Base64

class ImageValidationError(ValueError):
    """Raised when an uploaded crop photo fails validation."""
    def __init__(self, message: str, error_type: str = "validation_error"):
        super().__init__(message)
        self.message = message
        self.error_type = error_type

class ImageValidator:
    @staticmethod
    def get_error_message(error_key: str, language: str) -> str:
        lang = language[:2].lower() if language else "en"
        if lang not in SUPPORTED_LANGUAGES:
            lang = "en"
        return IMAGE_ERROR_MESSAGES.get(error_key, {}).get(lang, IMAGE_ERROR_MESSAGES[error_key]["en"])

    @staticmethod
    def detect_format_from_bytes(data: bytes, language: str = "en") -> str:
        """
        Inspects binary magic bytes to determine verified MIME type.
        Supports only JPEG, PNG, and WebP.
        """
        if len(data) < 12:
            raise ImageValidationError(
                ImageValidator.get_error_message("corrupt", language),
                error_type="corrupt"
            )

        # JPEG magic bytes: FF D8 FF
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"

        # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"

        # WebP magic bytes: RIFF .... WEBP
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"

        # Explicit rejection of other formats (GIF, BMP, TIFF, SVG, HTML)
        raise ImageValidationError(
            ImageValidator.get_error_message("unsupported_format", language),
            error_type="unsupported_format"
        )

    @classmethod
    def validate_crop_image(cls, image_input: Optional[str], language: str = "en") -> Tuple[bytes, str]:
        """
        Validates, decodes, and verifies an uploaded crop photo.
        Returns:
            Tuple of (validated_raw_bytes, verified_mime_type)
        Raises:
            ImageValidationError if invalid, oversized, unsupported, or corrupt.
        """
        if image_input is None:
            raise ImageValidationError(
                cls.get_error_message("empty", language),
                error_type="empty"
            )

        cleaned_str = image_input.strip()
        if not cleaned_str:
            raise ImageValidationError(
                cls.get_error_message("empty", language),
                error_type="empty"
            )

        # Handle data URL prefix if present (e.g., 'data:image/jpeg;base64,...')
        b64_payload = cleaned_str
        if "," in cleaned_str:
            _, b64_payload = cleaned_str.split(",", 1)
            b64_payload = b64_payload.strip()

        if not b64_payload:
            raise ImageValidationError(
                cls.get_error_message("empty", language),
                error_type="empty"
            )

        # Quick length pre-check before decoding
        if len(b64_payload) > MAX_BASE64_LENGTH:
            logger.warning(f"Rejected oversized base64 image payload: length={len(b64_payload)}")
            raise ImageValidationError(
                cls.get_error_message("oversized", language),
                error_type="oversized"
            )

        # Strict Base64 decoding
        try:
            raw_bytes = base64.b64decode(b64_payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            logger.warning(f"Failed to decode base64 image: {exc}")
            raise ImageValidationError(
                cls.get_error_message("malformed_base64", language),
                error_type="malformed_base64"
            )

        # Verify decoded byte size
        raw_size = len(raw_bytes)
        if raw_size == 0:
            raise ImageValidationError(
                cls.get_error_message("empty", language),
                error_type="empty"
            )

        if raw_size > MAX_RAW_IMAGE_BYTES:
            logger.warning(f"Rejected oversized raw image: bytes={raw_size} > {MAX_RAW_IMAGE_BYTES}")
            raise ImageValidationError(
                cls.get_error_message("oversized", language),
                error_type="oversized"
            )

        # Inspect actual binary signature (magic bytes)
        verified_mime = cls.detect_format_from_bytes(raw_bytes, language=language)

        # Internal image integrity check via Pillow
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            img.verify()
            detected_format = (img.format or "").upper()
            if detected_format not in ["JPEG", "PNG", "WEBP"]:
                raise ImageValidationError(
                    cls.get_error_message("unsupported_format", language),
                    error_type="unsupported_format"
                )
        except ImageValidationError:
            raise
        except Exception as exc:
            logger.warning(f"Pillow verification failed on image: {exc}")
            raise ImageValidationError(
                cls.get_error_message("corrupt", language),
                error_type="corrupt"
            )

        logger.info(f"Image validated successfully: mime={verified_mime}, size_bytes={raw_size}")
        return raw_bytes, verified_mime

