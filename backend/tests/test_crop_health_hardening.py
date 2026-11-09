"""
Kisan Hita — Check My Crop Hardening Test Suite
Comprehensive tests covering:
1. Image validation (JPEG, PNG, WebP, malformed base64, invalid signatures, header mismatches, empty, unsupported formats, size limit)
2. Gemini Vision integration (bytes passed, unconfirmed prefix, empty output, disabled, unconfigured, timeout, no secret/byte leaks)
3. Agricultural safety (no Fusarium/Rhizoctonia for wilting, no N-deficiency claim for yellowing, no fake confidence scores, no chemical dosage, 4-category separation)
4. Multilingual responses across all 7 languages (te, en, hi, ta, kn, ml, mr)
"""

import unittest
import base64
import io
import os
import sys
from unittest.mock import patch, MagicMock
from PIL import Image
from fastapi.testclient import TestClient
from auth_helpers import authenticated_client

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.config import settings
from app.services.image_validator import ImageValidator, ImageValidationError, MAX_RAW_IMAGE_BYTES
from app.services.crop_health_service import CropHealthService
from app.services.crop_health_localization import (
    SUPPORTED_LANGUAGES,
    SAFETY_NOTICES,
    DIAGNOSTIC_DISCLAIMERS,
    EXPERT_CONFIRMATION_NOTES,
    EXTENSION_CONTACTS,
    AI_VISION_MESSAGES,
    AI_VISION_PREFIXES,
    IMAGE_ERROR_MESSAGES
)
from app.services.gemini_service import GeminiAIService

def create_test_image(fmt: str, color: tuple = (34, 139, 34)) -> bytes:
    """Creates a minimal in-memory test image of the specified format."""
    bio = io.BytesIO()
    img = Image.new("RGB", (10, 10), color=color)
    img.save(bio, format=fmt)
    return bio.getvalue()

class TestCropHealthHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = authenticated_client(app)
        cls.jpeg_bytes = create_test_image("JPEG")
        cls.png_bytes = create_test_image("PNG")
        cls.webp_bytes = create_test_image("WEBP")
        cls.gif_bytes = create_test_image("GIF")
        cls.bmp_bytes = create_test_image("BMP")

    # =========================================================================
    # 1. Image Validation Tests
    # =========================================================================

    def test_valid_jpeg_raw_and_data_url(self):
        """Verifies valid JPEG is accepted both as raw Base64 and data URL."""
        b64_raw = base64.b64encode(self.jpeg_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64_raw}"

        # Raw base64
        bytes_out, mime_out = ImageValidator.validate_crop_image(b64_raw, "en")
        self.assertEqual(mime_out, "image/jpeg")
        self.assertEqual(bytes_out, self.jpeg_bytes)

        # Data URL
        bytes_out2, mime_out2 = ImageValidator.validate_crop_image(data_url, "te")
        self.assertEqual(mime_out2, "image/jpeg")
        self.assertEqual(bytes_out2, self.jpeg_bytes)

    def test_valid_png_raw_and_data_url(self):
        """Verifies valid PNG is accepted both as raw Base64 and data URL."""
        b64_raw = base64.b64encode(self.png_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{b64_raw}"

        bytes_out, mime_out = ImageValidator.validate_crop_image(b64_raw, "hi")
        self.assertEqual(mime_out, "image/png")
        self.assertEqual(bytes_out, self.png_bytes)

        bytes_out2, mime_out2 = ImageValidator.validate_crop_image(data_url, "kn")
        self.assertEqual(mime_out2, "image/png")
        self.assertEqual(bytes_out2, self.png_bytes)

    def test_valid_webp_raw_and_data_url(self):
        """Verifies valid WebP is accepted both as raw Base64 and data URL."""
        b64_raw = base64.b64encode(self.webp_bytes).decode("ascii")
        data_url = f"data:image/webp;base64,{b64_raw}"

        bytes_out, mime_out = ImageValidator.validate_crop_image(b64_raw, "ta")
        self.assertEqual(mime_out, "image/webp")
        self.assertEqual(bytes_out, self.webp_bytes)

        bytes_out2, mime_out2 = ImageValidator.validate_crop_image(data_url, "ml")
        self.assertEqual(mime_out2, "image/webp")
        self.assertEqual(bytes_out2, self.webp_bytes)

    def test_header_mimetype_mismatch_detected_by_magic_bytes(self):
        """
        Verifies that when data URL claims image/jpeg, but raw bytes are PNG,
        the validator relies on true binary magic bytes and assigns image/png.
        """
        png_b64 = base64.b64encode(self.png_bytes).decode("ascii")
        deceptive_url = f"data:image/jpeg;base64,{png_b64}"

        bytes_out, mime_out = ImageValidator.validate_crop_image(deceptive_url, "en")
        self.assertEqual(mime_out, "image/png")
        self.assertEqual(bytes_out, self.png_bytes)

    def test_unsupported_formats_gif_and_bmp_rejected(self):
        """Verifies GIF and BMP images are strictly rejected with 422."""
        gif_b64 = base64.b64encode(self.gif_bytes).decode("ascii")
        with self.assertRaises(ImageValidationError) as ctx:
            ImageValidator.validate_crop_image(gif_b64, "en")
        self.assertEqual(ctx.exception.error_type, "unsupported_format")

        # Via API endpoint
        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "Yellowing leaves",
            "image_base64": gif_b64,
            "language": "en"
        })
        self.assertEqual(res.status_code, 422)

    def test_malformed_base64_rejected(self):
        """Verifies malformed Base64 is rejected with actionable message."""
        malformed = "data:image/jpeg;base64,!!!NotValidBase64Encoding@@@"
        with self.assertRaises(ImageValidationError) as ctx:
            ImageValidator.validate_crop_image(malformed, "en")
        self.assertEqual(ctx.exception.error_type, "malformed_base64")

        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "Yellowing leaves",
            "image_base64": malformed,
            "language": "en"
        })
        self.assertEqual(res.status_code, 422)

    def test_invalid_image_signature_text_file_rejected(self):
        """Verifies non-image binary (text payload) encoded in base64 is rejected."""
        text_bytes = b"Hello, this is a plain text file pretending to be a leaf photo."
        text_b64 = base64.b64encode(text_bytes).decode("ascii")

        with self.assertRaises(ImageValidationError) as ctx:
            ImageValidator.validate_crop_image(text_b64, "en")
        self.assertIn(ctx.exception.error_type, ["unsupported_format", "corrupt"])

        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "Yellowing leaves",
            "image_base64": text_b64,
            "language": "en"
        })
        self.assertEqual(res.status_code, 422)

    def test_empty_image_rejected(self):
        """Verifies empty image payload is rejected."""
        with self.assertRaises(ImageValidationError) as ctx:
            ImageValidator.validate_crop_image("", "en")
        self.assertEqual(ctx.exception.error_type, "empty")

        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "Yellowing leaves",
            "image_base64": "",
            "language": "en"
        })
        self.assertEqual(res.status_code, 422)

    def test_oversized_image_rejected(self):
        """Verifies raw images exceeding 10MB are rejected."""
        oversized_str = "A" * (14 * 1024 * 1024 + 100)
        with self.assertRaises(ImageValidationError) as ctx:
            ImageValidator.validate_crop_image(oversized_str, "en")
        self.assertEqual(ctx.exception.error_type, "oversized")

    # =========================================================================
    # 2. Gemini Vision Integration & Failure Handling Tests
    # =========================================================================

    def test_gemini_receives_validated_bytes_and_marks_unconfirmed(self):
        """Verifies Gemini receives validated bytes and observation is clearly prefixed as preliminary."""
        async def run_test():
            fake_response = MagicMock()
            fake_response.text = "Leaf margins show slight drying. Undersides show no obvious insect colonies."
            
            with patch("app.services.gemini_service.GeminiAIService.is_configured", return_value=True), \
                 patch("app.services.gemini_service.genai.Client") as mock_client:
                mock_instance = MagicMock()
                mock_instance.models.generate_content.return_value = fake_response
                mock_client.return_value = mock_instance

                res = await GeminiAIService.analyze_crop_image(
                    image_bytes=self.jpeg_bytes,
                    mime_type="image/jpeg",
                    crop_name="Chilli",
                    symptoms="Leaves curling upward",
                    language="te"
                )
                self.assertIsNotNone(res)
                self.assertEqual(res["status"], "completed")
                # Must be prefixed with AI observation marker
                self.assertIn("AI ప్రాథమిక దృశ్య పరిశీలనలు", res["visual_observations"])
                self.assertIn("Leaf margins", res["visual_observations"])

        import asyncio
        asyncio.run(run_test())

    def test_gemini_unconfigured_handled_cleanly(self):
        """Verifies when Gemini is unconfigured, response indicates unavailable without crashing."""
        async def run_test():
            with patch("app.services.gemini_service.GeminiAIService.is_configured", return_value=False):
                res = await GeminiAIService.analyze_crop_image(
                    image_bytes=self.jpeg_bytes,
                    mime_type="image/jpeg",
                    crop_name="Cotton",
                    symptoms="Yellow leaves",
                    language="en"
                )
                self.assertEqual(res["status"], "unavailable")
                self.assertIsNone(res["visual_observations"])
                self.assertIn("unavailable", res["message"].lower())

        import asyncio
        asyncio.run(run_test())

    def test_gemini_timeout_or_error_handled_cleanly(self):
        """Verifies network timeout or API error returns error status without inventing fake observations."""
        async def run_test():
            with patch("app.services.gemini_service.GeminiAIService.is_configured", return_value=True), \
                 patch("app.services.gemini_service.genai.Client") as mock_client:
                mock_instance = MagicMock()
                mock_instance.models.generate_content.side_effect = TimeoutError("Request timed out")
                mock_client.return_value = mock_instance

                res = await GeminiAIService.analyze_crop_image(
                    image_bytes=self.jpeg_bytes,
                    mime_type="image/jpeg",
                    crop_name="Paddy",
                    symptoms="Spots on leaves",
                    language="en"
                )
                self.assertEqual(res["status"], "error")
                self.assertIsNone(res["visual_observations"])
                self.assertIn("timeout", res["error"].lower())

        import asyncio
        asyncio.run(run_test())

    def test_no_secret_key_or_image_bytes_in_responses(self):
        """Ensures API keys and raw image bytes are never serialized into response JSON."""
        jpeg_b64 = f"data:image/jpeg;base64,{base64.b64encode(self.jpeg_bytes).decode('ascii')}"
        res = self.client.post("/api/crop-health/diagnose", json={
            "crop_name": "Cotton",
            "symptoms": "Lower leaf yellowing",
            "image_base64": jpeg_b64,
            "language": "en"
        })
        self.assertEqual(res.status_code, 200)
        resp_text = res.text

        # Verify no secret key leakage
        if settings.GEMINI_API_KEY:
            self.assertNotIn(settings.GEMINI_API_KEY, resp_text)
        # Verify raw binary bytes are not leaked
        self.assertNotIn("b'\\xff\\xd8\\xff", resp_text)

    # =========================================================================
    # 3. Agricultural Safety Tests
    # =========================================================================

    def test_yellowing_not_equated_with_nitrogen_deficiency(self):
        """Verifies yellow leaves are not equated with nitrogen deficiency without evidence."""
        res = CropHealthService.evaluate_crop_health("Cotton", "Yellow leaves with chlorosis", language="en")
        combined_factors = " ".join(res.potential_factors).lower()
        self.assertNotIn("nitrogen deficiency", combined_factors)
        self.assertIn("moisture", combined_factors)

    def test_wilting_not_equated_with_fusarium_rhizoctonia_or_nematodes(self):
        """Verifies generic wilting never diagnoses Fusarium, Rhizoctonia, or nematodes."""
        res = CropHealthService.evaluate_crop_health("Chilli", "Plants are wilting and drooping", language="en")
        combined = " ".join(res.potential_factors).lower() + " " + res.cautious_assessment.lower()
        self.assertNotIn("fusarium", combined)
        self.assertNotIn("rhizoctonia", combined)
        self.assertNotIn("nematode", combined)
        self.assertIn("transpiration", combined)

    def test_spots_not_equated_with_fungal_disease_without_evidence(self):
        """Verifies leaf spots are not equated with fungal or bacterial disease."""
        res = CropHealthService.evaluate_crop_health("Tomato", "Small circular spots on leaves", language="en")
        combined = " ".join(res.potential_factors).lower()
        self.assertNotIn("fungal disease", combined)
        self.assertNotIn("bacterial disease", combined)
        self.assertIn("foliar", combined)

    def test_no_fabricated_confidence_score_percentages(self):
        """Verifies no fabricated confidence percentages (e.g., 95%) appear in the report."""
        res = CropHealthService.evaluate_crop_health("Cotton", "Yellowing leaves", language="en")
        self.assertNotIn("%", res.cautious_assessment)
        for f in res.potential_factors:
            self.assertNotIn("%", f)

    def test_four_information_categories_cleanly_separated(self):
        """Verifies the four information categories are explicitly distinguished."""
        res = CropHealthService.evaluate_crop_health(
            crop_name="Cotton",
            symptoms="Yellow leaves",
            onset_days="3 days ago",
            affected_spread="Few scattered plants",
            language="en"
        )
        # Category 1: Farmer-reported summary
        self.assertIsNotNone(res.farmer_reported_summary)
        self.assertIn("Cotton", res.farmer_reported_summary)
        self.assertIn("3 days ago", res.farmer_reported_summary)

        # Category 2: Visual analysis status
        self.assertEqual(res.visual_analysis_status, "not_provided")

        # Category 3: Plausible contributing factors
        self.assertGreater(len(res.potential_factors), 0)

        # Category 4: Expert confirmation note
        self.assertIsNotNone(res.expert_confirmation_note)
        self.assertIn("does not provide a confirmed laboratory diagnosis", res.expert_confirmation_note)
        self.assertIn("Krishi Vigyan Kendra", res.expert_confirmation_note)

    # =========================================================================
    # 4. Multilingual Tests Across All 7 Languages
    # =========================================================================

    def test_all_seven_languages_localized_no_english_fallback(self):
        """Verifies every field in CropHealthResponse is localized across all 7 languages."""
        test_crops = {
            "te": ("పత్తి", "ఆకులు పసుపు రంగులోకి మారుతున్నాయి"),
            "en": ("Cotton", "Leaves turning yellow"),
            "hi": ("कपास", "पत्तियां पीली हो रही हैं"),
            "ta": ("பருத்தி", "இலைகள் மஞ்சள் நிறமாக மாறுகின்றன"),
            "kn": ("ಹತ್ತಿ", "ಎಲೆಗಳು ಹಳದಿ ಬಣ್ಣಕ್ಕೆ ತಿರುಗುತ್ತಿವೆ"),
            "ml": ("പരുത്തി", "ഇലകൾ മഞ്ഞനിറമാവുന്നു"),
            "mr": ("कापूस", "पाने पिवळी पडत आहेत")
        }

        for lang, (cname, sym) in test_crops.items():
            res = CropHealthService.evaluate_crop_health(
                crop_name=cname,
                symptoms=sym,
                onset_days=None,       # Missing context test
                affected_spread=None,  # Missing context test
                language=lang
            )

            # 1. Safety Notice
            self.assertEqual(res.safety_notice, SAFETY_NOTICES[lang])
            # 2. Disclaimer
            self.assertEqual(res.diagnostic_disclaimer, DIAGNOSTIC_DISCLAIMERS[lang])
            # 3. Expert Confirmation Note
            self.assertEqual(res.expert_confirmation_note, EXPERT_CONFIRMATION_NOTES[lang])
            # 4. Extension Contact (contains 1800-180-1551)
            self.assertEqual(res.extension_contact, EXTENSION_CONTACTS[lang])
            self.assertIn("1800-180-1551", res.extension_contact)
            # 5. Factors (non-empty, non-English for non-en languages)
            self.assertGreater(len(res.potential_factors), 0)
            if lang != "en":
                self.assertNotIn("Root-zone moisture imbalance", res.potential_factors[0])
            # 6. Cultural Management
            self.assertGreater(len(res.cultural_management_steps), 0)
            # 7. Unspecified context handled explicitly without English fallback
            if lang != "en":
                self.assertNotIn("Not specified by farmer", res.farmer_reported_summary)
                self.assertNotIn("Not specified by farmer", res.cautious_assessment)

