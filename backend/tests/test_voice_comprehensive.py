import unittest
import asyncio
import base64
import os
import sys
from unittest.mock import patch
import speech_recognition as sr
from fastapi.testclient import TestClient
from auth_helpers import authenticated_client

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.config import settings
from app.services.gnani_voice import (
    generate_mock_wav,
    get_voice_provider,
    MockGnaniProvider,
    LiveGnaniProvider,
    GNANI_LANG_MAP,
    TIMBRE_V30_VOICES
)
from app.services.gnani_voice import DormantGnaniVoiceProvider, detect_gnani_audio_mime

class TestVoiceModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = authenticated_client(app)
        cls.valid_wav = generate_mock_wav(0.3)
        cls.valid_b64 = base64.b64encode(cls.valid_wav).decode("utf-8")

    def test_voice_imports_and_initialization(self):
        """Verifies voice providers and language mappings are properly initialized."""
        provider = get_voice_provider()
        self.assertIsInstance(provider, MockGnaniProvider)
        self.assertEqual(len(GNANI_LANG_MAP), 7)
        self.assertEqual(len(TIMBRE_V30_VOICES), 13)
        self.assertEqual(GNANI_LANG_MAP["te"], "te-IN")
        self.assertIn("Vasudha", TIMBRE_V30_VOICES)

    def test_mock_stt_request_and_response(self):
        """Tests STT REST endpoint with valid base64 audio across multiple languages."""
        with patch.object(sr.Recognizer, "recognize_google", return_value="రైతులకు నమస్కారం"):
            for lang in ["te", "en", "hi", "ta", "kn", "ml", "mr"]:
                res = self.client.post("/api/voice/stt", json={
                    "audio_base64": self.valid_b64,
                    "language": lang
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertFalse(data["is_mock"])
                self.assertEqual(data["model"], "temporary-local-stt")
                self.assertGreater(len(data["transcript"]), 0)
                self.assertIsNone(data["confidence"])

    def test_mock_tts_request_and_response(self):
        """Tests TTS REST endpoint with valid text and receives genuine playable WAV audio."""
        for lang, expected_voice in [("te", "Geeta"), ("hi", "Lekha"), ("en", "Rishi")]:
            res = self.client.post("/api/voice/tts", json={
                "text": "రైతులకు నమస్కారం, ఇది పరీక్ష సందేశం.",
                "language": lang
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertFalse(data["is_mock"])
            self.assertEqual(data["model"], "temporary-local-tts")
            self.assertEqual(data["voice_name"], expected_voice)
            self.assertEqual(data["format"], "audio/wav")
            # Verify audio_base64 is a valid WAV
            audio_bytes = base64.b64decode(data["audio_base64"])
            self.assertEqual(audio_bytes[:4], b"RIFF")
            self.assertEqual(audio_bytes[8:12], b"WAVE")

    def test_invalid_audio_input_handling(self):
        """Verifies proper HTTP 400 error when audio is malformed or too short."""
        # Empty string
        res1 = self.client.post("/api/voice/stt", json={"audio_base64": "", "language": "en"})
        self.assertEqual(res1.status_code, 400)
        
        # Corrupted base64
        res2 = self.client.post("/api/voice/stt", json={"audio_base64": "!!!not_valid_b64!!!", "language": "en"})
        self.assertEqual(res2.status_code, 400)
        
        # Audio bytes smaller than 44-byte header
        tiny_b64 = base64.b64encode(b"short").decode("utf-8")
        res3 = self.client.post("/api/voice/stt", json={"audio_base64": tiny_b64, "language": "en"})
        self.assertEqual(res3.status_code, 400)

    def test_unsupported_language_handling(self):
        """Verifies HTTP 422 error when unsupported language is passed."""
        res = self.client.post("/api/voice/stt", json={
            "audio_base64": self.valid_b64,
            "language": "unsupported_xyz"
        })
        self.assertEqual(res.status_code, 422)
        self.assertTrue(
            any("Unsupported language" in str(err) for err in res.json().get("detail", []))
            or "Unsupported language" in str(res.json())
        )

    def test_empty_text_in_tts(self):
        """Verifies HTTP 400 error when text input is empty, whitespace, or empty after symbol stripping."""
        # Pure whitespace
        res1 = self.client.post("/api/voice/tts", json={"text": "   ", "language": "en"})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("cannot be empty", res1.json()["detail"])

        # Empty string
        res2 = self.client.post("/api/voice/tts", json={"text": "", "language": "en"})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("cannot be empty", res2.json()["detail"])

        # Markdown/symbol only string that becomes empty after stripping
        res3 = self.client.post("/api/voice/tts", json={"text": " * # ` ", "language": "en"})
        self.assertIn(res3.status_code, [400, 422])
        self.assertIn("cannot be empty", str(res3.json()))

    def test_tts_length_boundary_and_resilience(self):
        """Verifies TTS handles long texts from assistant/crop reports (up to 2000 chars) gracefully."""
        # 600-character text (typical Crop Advisor / Check Crop readout)
        long_text_600 = "Farmer advisory: " + ("Paddy crop requires steady water management. " * 12)
        self.assertGreater(len(long_text_600), 550)
        res600 = self.client.post("/api/voice/tts", json={"text": long_text_600, "language": "en"})
        self.assertEqual(res600.status_code, 200)
        self.assertIn("audio_base64", res600.json())

        # 1500-character text (typical detailed assistant response)
        long_text_1500 = "Agricultural advisory summary: " + ("Healthy soil requires balanced nitrogen and phosphorus. " * 30)
        self.assertGreater(len(long_text_1500), 1200)
        res1500 = self.client.post("/api/voice/tts", json={"text": long_text_1500, "language": "en"})
        self.assertEqual(res1500.status_code, 200)
        self.assertIn("audio_base64", res1500.json())

        # Text exceeding 2000 characters -> HTTP 422 (Pydantic validation limit)
        oversized = "X" * 2001
        res_over = self.client.post("/api/voice/tts", json={"text": oversized, "language": "en"})
        self.assertEqual(res_over.status_code, 422)

    def test_tts_invalid_and_missing_payloads(self):
        """Verifies HTTP 422 validation errors for missing, null, or out-of-bound fields."""
        # Missing text field entirely
        res_missing = self.client.post("/api/voice/tts", json={"language": "en"})
        self.assertEqual(res_missing.status_code, 422)

        # None/null text
        res_none = self.client.post("/api/voice/tts", json={"text": None, "language": "en"})
        self.assertEqual(res_none.status_code, 422)

        # Speed out of bounds (< 0.5 or > 2.0)
        res_speed = self.client.post("/api/voice/tts", json={"text": "Hello", "speed": 3.0})
        self.assertEqual(res_speed.status_code, 422)

        # Unsupported language code
        res_lang = self.client.post("/api/voice/tts", json={"text": "Hello", "language": "spanish"})
        self.assertEqual(res_lang.status_code, 422)

    def test_all_7_languages_tts_and_locale_tags(self):
        """Available system voices synthesize speech; unsupported ones do not use another language's voice."""
        for lang in ["te", "en", "hi", "ta", "kn", "te-IN", "hi-IN"]:
            res = self.client.post("/api/voice/tts", json={"text": "నమస్కారం రైతు సోదరులకు", "language": lang})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["format"], "audio/wav")
            self.assertIsNotNone(res.json()["voice_name"])

        for lang in ["ml", "mr"]:
            res = self.client.post("/api/voice/tts", json={"text": "నమస్కారం రైతు సోదరులకు", "language": lang})
            self.assertEqual(res.status_code, 503)
            self.assertIn("No verified local system voice", res.json()["detail"])

    def test_live_gnani_calls_blocked_when_disabled(self):
        """CRITICAL: Verifies live Gnani API calls raise an error when GNANI_LIVE_ENABLED=false."""
        self.assertFalse(settings.GNANI_LIVE_ENABLED)
        live_provider = LiveGnaniProvider()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Attempt both modalities with a patched HTTP client to prove no outbound request occurs.
        with patch("app.services.gnani_voice.httpx.AsyncClient") as client:
            with self.assertRaises(RuntimeError) as ctx1:
                loop.run_until_complete(live_provider.speech_to_text(self.valid_wav, "en"))
            with self.assertRaises(RuntimeError) as ctx2:
                loop.run_until_complete(live_provider.text_to_speech("test", "en"))
            self.assertEqual(client.call_count, 0)
        self.assertIn("Gnani integration is dormant during development to protect credits", str(ctx1.exception))
        self.assertIn("Gnani integration is dormant during development to protect credits", str(ctx2.exception))
        
        loop.close()

    def test_live_gnani_missing_credentials(self):
        """Verifies LiveGnaniProvider raises descriptive error if enabled but API key is missing."""
        original_state = settings.GNANI_LIVE_ENABLED
        original_prisma = settings.GNANI_PRISMA_ENABLED
        original_key = settings.GNANI_API_KEY
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_API_KEY = ""
            live_provider = LiveGnaniProvider()
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            with self.assertRaises(RuntimeError) as ctx:
                loop.run_until_complete(live_provider.speech_to_text(self.valid_wav, "en"))
            self.assertIn("Gnani API Key is missing", str(ctx.exception))
            
            loop.close()
        finally:
            settings.GNANI_LIVE_ENABLED = original_state
            settings.GNANI_PRISMA_ENABLED = original_prisma
            settings.GNANI_API_KEY = original_key

    def test_gnani_flags_are_independent_and_global_master_wins(self):
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED)
        try:
            settings.GNANI_LIVE_ENABLED = False
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_TIMBRE_ENABLED = True
            self.assertIsInstance(get_voice_provider("stt"), MockGnaniProvider)
            self.assertIsInstance(get_voice_provider("tts"), MockGnaniProvider)
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_TIMBRE_ENABLED = False
            self.assertIsInstance(get_voice_provider("stt"), DormantGnaniVoiceProvider)
            self.assertIsInstance(get_voice_provider("tts"), MockGnaniProvider)
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED = original

    def test_direct_provider_calls_respect_each_modality_switch(self):
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED)
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = False
            settings.GNANI_TIMBRE_ENABLED = False
            with patch("app.services.gnani_voice.httpx.AsyncClient") as client:
                with self.assertRaisesRegex(RuntimeError, "Prisma is disabled"):
                    asyncio.run(DormantGnaniVoiceProvider().speech_to_text(self.valid_wav, "en"))
                with self.assertRaisesRegex(RuntimeError, "Timbre is disabled"):
                    asyncio.run(DormantGnaniVoiceProvider().text_to_speech("hello", "en", voice="Vasudha"))
                client.assert_not_called()
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED = original

    def test_prisma_formats_and_webm_is_never_mislabeled(self):
        self.assertEqual(detect_gnani_audio_mime(self.valid_wav), "audio/wav")
        self.assertEqual(detect_gnani_audio_mime(b"ID3" + b"\0" * 50), "audio/mpeg")
        self.assertEqual(detect_gnani_audio_mime(b"OggS" + b"\0" * 50), "audio/ogg")
        self.assertEqual(detect_gnani_audio_mime(b"fLaC" + b"\0" * 50), "audio/flac")
        self.assertEqual(detect_gnani_audio_mime(b"\xff\xf1" + b"\0" * 50), "audio/aac")
        self.assertEqual(detect_gnani_audio_mime(b"\0\0\0\x18ftypM4A " + b"\0" * 50), "audio/mp4")
        self.assertEqual(detect_gnani_audio_mime(b"\x1a\x45\xdf\xa3" + b"\0" * 50), "audio/webm")

    def test_prisma_mock_response_contract_and_no_fabricated_confidence(self):
        class FakeResponse:
            status_code = 200
            def json(self):
                return {"success": True, "transcript": "Which crop suits cotton soil?", "model": "prisma-v3.0", "detected_language_code": "en-IN", "processing_time": 0.4}
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, url, **kwargs):
                self.kwargs = kwargs
                self.url = url
                return FakeResponse()
        fake = FakeClient()
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_API_KEY)
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_API_KEY = "test-only-not-a-real-key"
            with patch("app.services.gnani_voice.httpx.AsyncClient", return_value=fake):
                result = asyncio.run(DormantGnaniVoiceProvider().speech_to_text(self.valid_wav, "en"))
            self.assertEqual(fake.url, settings.GNANI_STT_URL)
            self.assertEqual(fake.kwargs["headers"]["X-API-Key-ID"], "test-only-not-a-real-key")
            self.assertIn("audio_file", fake.kwargs["files"])
            self.assertEqual(fake.kwargs["files"]["audio_file"][2], "audio/wav")
            self.assertEqual(fake.kwargs["data"], {"model": "prisma-v3.0", "language_code": "indic-auto", "format": "codemix"})
            self.assertEqual(result.transcript, "Which crop suits cotton soil?")
            self.assertIsNone(result.confidence)
            self.assertEqual(result.processing_time_ms, 400)
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_API_KEY = original

    def test_prisma_upload_duration_and_format_guards_precede_provider_call(self):
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_API_KEY)
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_API_KEY = "test-only-not-a-real-key"
            with patch("app.services.gnani_voice.httpx.AsyncClient") as http_client:
                too_long = self.client.post("/api/voice/stt/upload", files={"file": ("voice.wav", self.valid_wav, "audio/wav")}, data={"language": "en", "duration_seconds": "30.1"})
                self.assertEqual(too_long.status_code, 422)
                webm = self.client.post("/api/voice/stt/upload", files={"file": ("voice.webm", b"\x1a\x45\xdf\xa3" + b"\0" * 60, "audio/webm")}, data={"language": "en", "duration_seconds": "1"})
                self.assertEqual(webm.status_code, 422)
                self.assertEqual(http_client.call_count, 0)
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_API_KEY = original

    def test_disabled_prisma_and_timbre_make_no_gnani_http_requests(self):
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED)
        try:
            settings.GNANI_LIVE_ENABLED = False
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_TIMBRE_ENABLED = True
            with patch("app.services.gnani_voice.httpx.AsyncClient") as client:
                self.assertIsInstance(get_voice_provider("stt"), MockGnaniProvider)
                self.assertIsInstance(get_voice_provider("tts"), MockGnaniProvider)
                self.assertEqual(client.call_count, 0)
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED = original

    def test_timbre_mock_binary_audio_and_voice_language_validation(self):
        class FakeResponse:
            status_code = 200
            content = generate_mock_wav()
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, url, **kwargs):
                self.url, self.kwargs = url, kwargs
                return FakeResponse()
        fake = FakeClient()
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_TIMBRE_ENABLED, settings.GNANI_API_KEY, settings.GNANI_TIMBRE_VOICE_TE)
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_TIMBRE_ENABLED = True
            settings.GNANI_API_KEY = "test-only-not-a-real-key"
            settings.GNANI_TIMBRE_VOICE_TE = "Vasudha"
            with patch("app.services.gnani_voice.httpx.AsyncClient", return_value=fake):
                result = asyncio.run(DormantGnaniVoiceProvider().text_to_speech("నమస్కారం", "te"))
            self.assertEqual(fake.url, settings.GNANI_TTS_URL)
            self.assertEqual(fake.kwargs["headers"]["X-API-Key-ID"], "test-only-not-a-real-key")
            self.assertEqual(fake.kwargs["json"]["model"], "timbre-v3.0")
            self.assertEqual(fake.kwargs["json"]["voice"], "Vasudha")
            self.assertEqual(base64.b64decode(result.audio_base64)[:4], b"RIFF")
            with self.assertRaises(ValueError):
                asyncio.run(DormantGnaniVoiceProvider().text_to_speech("hello", "te", voice="Nalini"))
            with self.assertRaises(ValueError):
                asyncio.run(DormantGnaniVoiceProvider().text_to_speech("hello", "te", speed=1.2))
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_TIMBRE_ENABLED, settings.GNANI_API_KEY, settings.GNANI_TIMBRE_VOICE_TE = original

    def test_timbre_voice_catalog_is_shared_and_unselected_until_configured(self):
        language_fields = {
            "en-IN": "GNANI_TIMBRE_VOICE_EN", "te-IN": "GNANI_TIMBRE_VOICE_TE",
            "hi-IN": "GNANI_TIMBRE_VOICE_HI", "ta-IN": "GNANI_TIMBRE_VOICE_TA",
            "kn-IN": "GNANI_TIMBRE_VOICE_KN", "ml-IN": "GNANI_TIMBRE_VOICE_ML",
            "mr-IN": "GNANI_TIMBRE_VOICE_MR",
        }
        languages = {"en-IN": "en", "te-IN": "te", "hi-IN": "hi", "ta-IN": "ta", "kn-IN": "kn", "ml-IN": "ml", "mr-IN": "mr"}
        original = {field: getattr(settings, field) for field in language_fields.values()}
        original.update({"GNANI_LIVE_ENABLED": settings.GNANI_LIVE_ENABLED, "GNANI_TIMBRE_ENABLED": settings.GNANI_TIMBRE_ENABLED, "GNANI_API_KEY": settings.GNANI_API_KEY})
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_TIMBRE_ENABLED = True
            settings.GNANI_API_KEY = "test-only-not-a-real-key"
            for field in language_fields.values():
                setattr(settings, field, "")
            with patch("app.services.gnani_voice.httpx.AsyncClient") as http_client:
                for locale, field in language_fields.items():
                    with self.subTest(locale=locale):
                        with self.assertRaisesRegex(RuntimeError, "No Timbre v3.0 voice has been selected"):
                            asyncio.run(DormantGnaniVoiceProvider().text_to_speech("sample", languages[locale]))
                        with self.assertRaises(ValueError):
                            asyncio.run(DormantGnaniVoiceProvider().text_to_speech("sample", languages[locale], voice="not-a-catalogue-voice"))
                self.assertEqual(http_client.call_count, 0)

            class FakeResponse:
                status_code = 200
                content = generate_mock_wav()
            class FakeClient:
                async def __aenter__(self): return self
                async def __aexit__(self, *args): return False
                async def post(self, url, **kwargs):
                    self.url, self.kwargs = url, kwargs
                    return FakeResponse()
            for locale, field in language_fields.items():
                with self.subTest(locale=locale, configured=True):
                    voice = "Vasudha"
                    setattr(settings, field, voice)
                    fake = FakeClient()
                    with patch("app.services.gnani_voice.httpx.AsyncClient", return_value=fake):
                        response = asyncio.run(DormantGnaniVoiceProvider().text_to_speech("sample", languages[locale]))
                    self.assertEqual(fake.kwargs["json"]["language"], locale)
                    self.assertEqual(fake.kwargs["json"]["voice"], voice)
                    self.assertEqual(fake.kwargs["json"]["audio_config"], {
                        "encoding": "linear_pcm", "container": "wav", "num_channels": 1,
                        "sample_rate": 48000, "sample_width": 2,
                    })
                    self.assertEqual(response.model, "timbre-v3.0")
        finally:
            settings.GNANI_LIVE_ENABLED = original["GNANI_LIVE_ENABLED"]
            settings.GNANI_TIMBRE_ENABLED = original["GNANI_TIMBRE_ENABLED"]
            settings.GNANI_API_KEY = original["GNANI_API_KEY"]
            for field, value in original.items():
                if field.startswith("GNANI_TIMBRE_VOICE_"):
                    setattr(settings, field, value)

    def test_provider_timeout_and_malformed_responses_fail_without_fabrication(self):
        import httpx
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED, settings.GNANI_API_KEY, settings.GNANI_TIMBRE_VOICE_EN)
        class TimeoutClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, *args, **kwargs): raise httpx.ReadTimeout("private transport detail")
        class BadResponse:
            status_code = 200
            def json(self): return {"success": True, "transcript": None}
        class BadClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, *args, **kwargs): return BadResponse()
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_TIMBRE_ENABLED = True
            settings.GNANI_API_KEY = "test-only-not-a-real-key"
            settings.GNANI_TIMBRE_VOICE_EN = "Kaveri"
            with patch("app.services.gnani_voice.httpx.AsyncClient", return_value=TimeoutClient()):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    asyncio.run(DormantGnaniVoiceProvider().speech_to_text(self.valid_wav, "en"))
            with patch("app.services.gnani_voice.httpx.AsyncClient", return_value=BadClient()):
                with self.assertRaisesRegex(RuntimeError, "invalid transcription response"):
                    asyncio.run(DormantGnaniVoiceProvider().speech_to_text(self.valid_wav, "en"))
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED, settings.GNANI_API_KEY, settings.GNANI_TIMBRE_VOICE_EN = original

    def test_prisma_empty_transcript_is_valid_no_speech_response(self):
        class EmptyTranscriptResponse:
            status_code = 200
            def json(self): return {"success": True, "transcript": ""}
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, *args, **kwargs): return EmptyTranscriptResponse()
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_API_KEY)
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_API_KEY = "test-only-not-a-real-key"
            with patch("app.services.gnani_voice.httpx.AsyncClient", return_value=FakeClient()):
                result = asyncio.run(DormantGnaniVoiceProvider().speech_to_text(self.valid_wav, "en"))
            self.assertEqual(result.transcript, "")
            self.assertIsNone(result.confidence)
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_API_KEY = original

    def test_stt_file_upload_endpoint(self):
        """Tests multipart/form-data upload route /api/voice/stt/upload."""
        files = {
            "file": ("recorded.wav", self.valid_wav, "audio/wav")
        }
        data = {"language": "te"}
        with patch.object(sr.Recognizer, "recognize_google", return_value="వరి సాగు సలహా"):
            res = self.client.post("/api/voice/stt/upload", files=files, data=data)
            self.assertEqual(res.status_code, 200)
            resp_data = res.json()
            self.assertEqual(resp_data["language"], "te")
            self.assertEqual(resp_data["transcript"], "వరి సాగు సలహా")

    def test_voice_config_endpoint(self):
        """Verifies /api/voice/config accurately reports provider and credit protection."""
        res = self.client.get("/api/voice/config")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["live_enabled"])
        self.assertTrue(data["credits_protected"])
        self.assertEqual(data["provider"], "browser_native_with_local_tts_fallback")
        self.assertEqual(data["stt_engine"], "Browser Web Speech Recognition")
        self.assertEqual(data["available_voices"], [])
        # Ensure private endpoints are never leaked in public config
        self.assertNotIn("stt_endpoint", data)
        self.assertNotIn("tts_endpoint", data)

    def test_voice_config_reports_only_switches_that_can_activate_a_modality(self):
        original = (settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED)
        try:
            settings.GNANI_LIVE_ENABLED = True
            settings.GNANI_PRISMA_ENABLED = True
            settings.GNANI_TIMBRE_ENABLED = False
            data = self.client.get("/api/voice/config").json()
            self.assertTrue(data["prisma_enabled"])
            self.assertFalse(data["timbre_enabled"])
            self.assertIn("Prisma v3.0", data["stt_engine"])
            self.assertNotIn("Timbre v3.0", data["tts_engine"])
            self.assertNotIn("api_key", str(data).lower())
        finally:
            settings.GNANI_LIVE_ENABLED, settings.GNANI_PRISMA_ENABLED, settings.GNANI_TIMBRE_ENABLED = original

    def test_websocket_stt_stream(self):
        """Tests real-time WebSocket streaming /api/voice/ws/stt."""
        with patch.object(sr.Recognizer, "recognize_google", return_value="నమస్కారం"):
            with self.client.websocket_connect("/api/voice/ws/stt?language=hi") as ws:
                # Send audio bytes in chunks
                chunk = self.valid_wav[:len(self.valid_wav)//2]
                ws.send_bytes(chunk)
                msg1 = ws.receive_json()
                self.assertEqual(msg1["status"], "listening")
                
                # Send second chunk
                ws.send_bytes(self.valid_wav[len(self.valid_wav)//2:])
                msg2 = ws.receive_json()
                self.assertEqual(msg2["status"], "listening")
                
                # Send EOS
                ws.send_text("EOS")
                msg3 = ws.receive_json()
                self.assertEqual(msg3["status"], "completed")
                self.assertEqual(msg3["transcript"], "నమస్కారం")
                self.assertFalse(msg3["is_mock"])

if __name__ == "__main__":
    unittest.main()

