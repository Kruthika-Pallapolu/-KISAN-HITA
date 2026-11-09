
import unittest
import base64
from unittest.mock import patch

from auth_helpers import authenticated_client
from app.main import app
from app.models.schemas import TTSResponse


class FakeTimbreProvider:
    """In-memory provider. Never makes an HTTP or Gnani request."""

    def __init__(self):
        self.calls = []

    async def text_to_speech(
        self, *, text, language, voice, speed, http_client=None
    ):
        self.calls.append({
            "text": text,
            "language": language,
            "voice": voice,
            "speed": speed,
            "http_client": http_client,
        })

        fake_wav = (
            b"RIFF"
            + b"\x00\x00\x00\x00"
            + b"WAVE"
            + b"mock-audio"
        )

        return TTSResponse(
            audio_base64=base64.b64encode(fake_wav).decode("utf-8"),
            format="audio/wav",
            language=language,
            voice_name=voice or "Vasudha",
            model="timbre-v3.0",
            provider="gnani_live",
            is_mock=False,
        )


class TestTimbreRoutesMocked(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = authenticated_client(app)

    def test_all_seven_languages_use_vasudha_without_network(self):
        provider = FakeTimbreProvider()
        languages = ["te", "en", "hi", "ta", "kn", "ml", "mr"]

        with patch(
            "app.routers.voice.get_voice_provider",
            return_value=provider,
        ):
            for language in languages:
                response = self.client.post(
                    "/api/voice/tts",
                    json={
                        "text": "This is a safe mocked voice test.",
                        "language": language,
                        "voice": "Vasudha",
                        "speed": 1.0,
                    },
                )

                self.assertEqual(
                    response.status_code,
                    200,
                    f"{language}: {response.text}",
                )

                data = response.json()

                self.assertEqual(data["voice_name"], "Vasudha")
                self.assertEqual(data["model"], "timbre-v3.0")
                self.assertEqual(data["provider"], "gnani_live")
                self.assertFalse(data["is_mock"])
                self.assertEqual(data["format"], "audio/wav")
                self.assertTrue(data["audio_base64"])

        self.assertEqual(len(provider.calls), 7)

        self.assertEqual(
            [call["voice"] for call in provider.calls],
            ["Vasudha"] * 7,
        )

        self.assertEqual(
            [call["language"] for call in provider.calls],
            languages,
        )

    def test_empty_text_is_rejected_without_provider_call(self):
        provider = FakeTimbreProvider()

        with patch(
            "app.routers.voice.get_voice_provider",
            return_value=provider,
        ):
            response = self.client.post(
                "/api/voice/tts",
                json={
                    "text": "   ",
                    "language": "en",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(provider.calls, [])

    def test_invalid_speed_is_rejected_without_provider_call(self):
        provider = FakeTimbreProvider()

        with patch(
            "app.routers.voice.get_voice_provider",
            return_value=provider,
        ):
            response = self.client.post(
                "/api/voice/tts",
                json={
                    "text": "Safe mocked test.",
                    "language": "en",
                    "voice": "Vasudha",
                    "speed": 2.1,
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    unittest.main()
