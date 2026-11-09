
import abc
import base64
import io
import os
import subprocess
import tempfile
import time
import struct
import wave
import httpx
from typing import Optional, Dict, Tuple

from ..config import settings
from ..models.schemas import STTResponse, TTSResponse

try:
    import speech_recognition as sr
except ImportError:
    sr = None


INDIC_LANG_MAP: Dict[str, str] = {
    "te": "te-IN",
    "en": "en-IN",
    "hi": "hi-IN",
    "ta": "ta-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
}

LOCAL_SYSTEM_VOICES: Dict[str, str] = {
    "te": "Geeta",
    "hi": "Lekha",
    "ta": "Vani",
    "kn": "Soumya",
    "en": "Rishi",
}

GNANI_TIMBRE_V30_CATALOG: Tuple[str, ...] = (
    "Avinash", "Shivani", "Lakshmi", "Kalpana", "Shubham",
    "Prakash", "Devansh", "Yashraj", "Chetana", "Vasudha",
    "Riyaa", "Tarika", "Harshad",
)

GNANI_LANG_MAP = INDIC_LANG_MAP
TIMBRE_V30_VOICES = GNANI_TIMBRE_V30_CATALOG


def generate_mock_wav(
    duration_seconds: float = 0.4,
    sample_rate: int = 16000,
) -> bytes:
    """Generate a valid PCM WAV for tests only."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_samples = int(duration_seconds * sample_rate)

        for i in range(num_samples):
            import math
            sample = int(
                1200 * math.sin(2 * math.pi * 440 * (i / sample_rate))
            )
            wf.writeframesraw(struct.pack("<h", sample))

    return buf.getvalue()


class BaseVoiceProvider(abc.ABC):

    @abc.abstractmethod
    async def speech_to_text(
        self,
        audio_bytes: Optional[bytes],
        language: str,
    ) -> STTResponse:
        pass

    @abc.abstractmethod
    async def text_to_speech(
        self,
        text: str,
        language: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> TTSResponse:
        pass

    @abc.abstractmethod
    def get_provider_info(self) -> dict:
        pass


class LocalDevelopmentVoiceProvider(BaseVoiceProvider):
    """Temporary local development provider."""

    def get_provider_info(self) -> dict:
        return {
            "name": "Local Development Voice Provider",
            "type": "temporary_development",
            "stt_engine": "SpeechRecognition Google Free Engine",
            "tts_engine": "macOS Native Speech Engine",
            "indic_voices_available": {
                "te": "Geeta",
                "hi": "Lekha",
                "ta": "Vani",
                "kn": "Soumya",
                "en": "Rishi",
                "ml": "Browser-native voice only",
                "mr": "Browser-native voice only",
            },
            "gnani_status": "Dormant",
        }

    async def speech_to_text(
        self,
        audio_bytes: Optional[bytes],
        language: str,
    ) -> STTResponse:

        t0 = time.time()

        if not audio_bytes or len(audio_bytes) < 44:
            raise ValueError("Audio input is empty or too short.")

        lang_key = language[:2].lower()

        if lang_key not in INDIC_LANG_MAP:
            raise ValueError(f"Unsupported language: {language}")

        if not sr:
            raise RuntimeError(
                "Python speech_recognition module is unavailable."
            )

        try:
            recognizer = sr.Recognizer()

            with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                audio_data = recognizer.record(source)

            transcript = recognizer.recognize_google(
                audio_data,
                language=INDIC_LANG_MAP[lang_key],
            )

        except sr.UnknownValueError as exc:
            raise ValueError(
                "No recognizable speech detected. Please speak clearly."
            ) from exc

        except sr.RequestError as exc:
            raise RuntimeError(
                f"Speech recognition service unavailable: {exc}"
            ) from exc

        except Exception as exc:
            raise RuntimeError(
                f"Speech recognition failed: {exc}"
            ) from exc

        if not transcript or not transcript.strip():
            raise ValueError("No recognizable speech detected.")

        return STTResponse(
            transcript=transcript.strip(),
            language=language,
            confidence=None,
            model="temporary-local-stt",
            provider="temporary_development",
            is_mock=False,
            processing_time_ms=round(
                (time.time() - t0) * 1000, 2
            ),
        )

    async def text_to_speech(
        self,
        text: str,
        language: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> TTSResponse:

        if not text or not text.strip():
            raise ValueError("Text input cannot be empty.")

        lang_key = language[:2].lower()

        if lang_key not in INDIC_LANG_MAP:
            raise ValueError(f"Unsupported language: {language}")

        if lang_key not in LOCAL_SYSTEM_VOICES:
            raise RuntimeError(
                f"No verified local voice is configured for {lang_key}. "
                "Use a matching browser-native voice if available."
            )

        system_voice = voice or LOCAL_SYSTEM_VOICES[lang_key]

        if not (
            os.path.exists("/usr/bin/say")
            and os.path.exists("/usr/bin/afconvert")
        ):
            raise RuntimeError(
                "Local backend speech synthesis requires macOS."
            )

        clean_text = (
            text.replace("*", "")
            .replace("#", "")
            .replace("`", "")
            .strip()
        )

        if len(clean_text) > 500:
            clean_text = clean_text[:500] + "..."

        with tempfile.NamedTemporaryFile(
            suffix=".aiff",
            delete=False,
        ) as aiff_file:
            aiff_path = aiff_file.name

        wav_path = aiff_path.replace(".aiff", ".wav")

        try:
            result = subprocess.run(
                [
                    "/usr/bin/say",
                    "-v",
                    system_voice,
                    "-o",
                    aiff_path,
                    clean_text,
                ],
                capture_output=True,
                timeout=8,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    "macOS speech synthesis failed."
                )

            conversion = subprocess.run(
                [
                    "/usr/bin/afconvert",
                    "-f",
                    "WAVE",
                    "-d",
                    "LEI16",
                    aiff_path,
                    wav_path,
                ],
                capture_output=True,
                timeout=5,
            )

            if conversion.returncode != 0:
                raise RuntimeError("Audio conversion failed.")

            with open(wav_path, "rb") as audio_file:
                wav_bytes = audio_file.read()

            if not wav_bytes or len(wav_bytes) < 44:
                raise RuntimeError("Generated WAV audio is invalid.")

            audio_b64 = base64.b64encode(
                wav_bytes
            ).decode("utf-8")

        except Exception as exc:
            raise RuntimeError(
                f"Local TTS synthesis failed: {exc}"
            ) from exc

        finally:
            for path in (aiff_path, wav_path):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        return TTSResponse(
            audio_base64=audio_b64,
            format="audio/wav",
            language=language,
            voice_name=system_voice,
            model="temporary-local-tts",
            provider="temporary_development",
            is_mock=False,
        )


class DormantGnaniVoiceProvider(BaseVoiceProvider):
    """Gnani Prisma and Timbre provider."""

    def get_provider_info(self) -> dict:
        return {
            "name": "Gnani AI Vachana Provider",
            "type": "gnani_production",
            "status": "Controlled by live configuration",
            "stt_model": "prisma-v3.0",
            "tts_model": "timbre-v3.0",
            "configured_voices": "per-language backend settings",
        }

    async def speech_to_text(
        self,
        audio_bytes: Optional[bytes],
        language: str,
    ) -> STTResponse:

        if not settings.GNANI_LIVE_ENABLED:
            raise RuntimeError("Gnani live integration is disabled.")

        if not settings.GNANI_PRISMA_ENABLED:
            raise RuntimeError("Gnani Prisma is disabled.")

        if not settings.GNANI_API_KEY:
            raise RuntimeError("Gnani API key is missing.")

        if settings.GNANI_PRISMA_MODEL != "prisma-v3.0":
            raise RuntimeError("Only Prisma v3.0 is supported.")

        if not audio_bytes or len(audio_bytes) < 44:
            raise ValueError("Audio recording is empty or too short.")

        mime = detect_gnani_audio_mime(audio_bytes)

        if mime == "audio/webm":
            raise ValueError(
                "WebM is not supported by this Prisma integration."
            )

        extension = {
            "audio/wav": "wav",
            "audio/mpeg": "mp3",
            "audio/ogg": "ogg",
            "audio/flac": "flac",
            "audio/aac": "aac",
            "audio/mp4": "m4a",
        }[mime]

        if mime == "audio/wav":
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                    duration = wav.getnframes() / wav.getframerate()

                if duration > 30:
                    raise ValueError(
                        "Prisma accepts WAV recordings up to 30 seconds."
                    )

            except (wave.Error, ZeroDivisionError) as exc:
                raise ValueError("WAV recording is malformed.") from exc

        headers = {
            "X-API-Key-ID": settings.GNANI_API_KEY,
            "Accept": "application/json",
        }

        files = {
            "audio_file": (
                f"recording.{extension}",
                audio_bytes,
                mime,
            )
        }

        data = {
            "model": settings.GNANI_PRISMA_MODEL,
            "language_code": "indic-auto",
            "format": "codemix",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    settings.GNANI_STT_URL,
                    headers=headers,
                    files=files,
                    data=data,
                )

            if res.status_code != 200:
                raise RuntimeError(
                    f"Prisma request failed with HTTP {res.status_code}."
                )

            try:
                resp = res.json()
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    "Prisma returned invalid JSON."
                ) from exc

            if not isinstance(resp, dict):
                raise RuntimeError("Prisma returned an invalid response.")

            transcript = resp.get("transcript")

            if (
                resp.get("success") is not True
                or not isinstance(transcript, str)
            ):
                raise RuntimeError(
                    "Prisma returned an invalid transcription response."
                )

            response_model = resp.get("model")

            if (
                response_model is not None
                and response_model != settings.GNANI_PRISMA_MODEL
            ):
                raise RuntimeError(
                    "Prisma returned an unexpected model."
                )

            processing_ms = resp.get("processing_time")

            return STTResponse(
                transcript=transcript.strip(),
                language=language,
                confidence=None,
                model=settings.GNANI_PRISMA_MODEL,
                provider="gnani_live",
                is_mock=False,
                processing_time_ms=(
                    round(processing_ms * 1000, 2)
                    if isinstance(processing_ms, (int, float))
                    and processing_ms >= 0
                    else None
                ),
            )

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Prisma transcription timed out."
            ) from exc

        except httpx.HTTPError as exc:
            raise RuntimeError(
                "Prisma service could not be reached."
            ) from exc

    async def text_to_speech(
        self,
        text: str,
        language: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> TTSResponse:

        if not settings.GNANI_LIVE_ENABLED:
            raise RuntimeError("Gnani live integration is disabled.")

        if not settings.GNANI_TIMBRE_ENABLED:
            raise RuntimeError("Gnani Timbre is disabled.")

        if not settings.GNANI_API_KEY:
            raise RuntimeError("Gnani API key is missing.")

        if settings.GNANI_TIMBRE_MODEL != "timbre-v3.0":
            raise RuntimeError("Only Timbre v3.0 is supported.")

        lang_key = language[:2].lower()
        gnani_lang = INDIC_LANG_MAP.get(lang_key)

        if not gnani_lang:
            raise ValueError(f"Unsupported language: {language}")

        configured_voices = {
            "en-IN": settings.GNANI_TIMBRE_VOICE_EN,
            "te-IN": settings.GNANI_TIMBRE_VOICE_TE,
            "hi-IN": settings.GNANI_TIMBRE_VOICE_HI,
            "ta-IN": settings.GNANI_TIMBRE_VOICE_TA,
            "kn-IN": settings.GNANI_TIMBRE_VOICE_KN,
            "ml-IN": settings.GNANI_TIMBRE_VOICE_ML,
            "mr-IN": settings.GNANI_TIMBRE_VOICE_MR,
        }

        voice_name = (
            voice or configured_voices.get(gnani_lang) or ""
        ).strip()

        if not voice_name:
            raise RuntimeError(
                f"No Timbre v3.0 voice has been selected for {gnani_lang}."
            )

        if voice_name not in GNANI_TIMBRE_V30_CATALOG:
            raise ValueError(
                f"Voice '{voice_name}' is not in the Timbre v3.0 catalogue."
            )

        if not text or not text.strip():
            raise ValueError("Text input cannot be empty.")

        if not 0.85 <= speed <= 1.15:
            raise ValueError(
                "Timbre speed must be between 0.85 and 1.15."
            )

        # Direct provider calls use a standalone client.
        # Normal FastAPI requests pass the shared lifespan client.
        if http_client is None:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0)
            ) as standalone_client:
                return await self.text_to_speech(
                    text=text,
                    language=language,
                    voice=voice,
                    speed=speed,
                    http_client=standalone_client,
                )

        headers = {
            "X-API-Key-ID": settings.GNANI_API_KEY,
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "voice": voice_name,
            "model": settings.GNANI_TIMBRE_MODEL,
            "language": gnani_lang,
            "speed": speed,
            "audio_config": {
                "encoding": "linear_pcm",
                "container": "wav",
                "num_channels": 1,
                "sample_rate": 48000,
                "sample_width": 2,
            },
        }

        try:
            res = await http_client.post(
                settings.GNANI_TTS_URL,
                headers=headers,
                json=payload,
            )

            if (
                res.status_code == 200
                and res.content
                and res.content[:4] == b"RIFF"
                and res.content[8:12] == b"WAVE"
            ):
                audio_b64 = base64.b64encode(
                    res.content
                ).decode("utf-8")

                return TTSResponse(
                    audio_base64=audio_b64,
                    format="audio/wav",
                    language=language,
                    voice_name=voice_name,
                    model=settings.GNANI_TIMBRE_MODEL,
                    provider="gnani_live",
                    is_mock=False,
                )

            if res.status_code == 200:
                raise RuntimeError(
                    "Timbre returned an empty or invalid WAV response."
                )

            raise RuntimeError(
                f"Timbre request failed with HTTP {res.status_code}."
            )

        except httpx.TimeoutException as exc:
            raise RuntimeError("Timbre synthesis timed out.") from exc

        except httpx.HTTPError as exc:
            raise RuntimeError(
                "Timbre service could not be reached."
            ) from exc


def detect_gnani_audio_mime(audio_bytes: bytes) -> str:
    """Identify audio formats by their actual signatures."""

    if (
        len(audio_bytes) >= 12
        and audio_bytes[:4] == b"RIFF"
        and audio_bytes[8:12] == b"WAVE"
    ):
        return "audio/wav"

    if audio_bytes.startswith(b"OggS"):
        return "audio/ogg"

    if audio_bytes.startswith(b"fLaC"):
        return "audio/flac"

    if (
        len(audio_bytes) >= 2
        and audio_bytes[0] == 0xFF
        and audio_bytes[1] & 0xF6 == 0xF0
    ):
        return "audio/aac"

    if audio_bytes.startswith(b"ID3") or (
        len(audio_bytes) >= 2
        and audio_bytes[0] == 0xFF
        and audio_bytes[1] & 0xE0 == 0xE0
    ):
        return "audio/mpeg"

    if len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
        return "audio/mp4"

    if (
        len(audio_bytes) >= 4
        and audio_bytes[:4] == b"\x1a\x45\xdf\xa3"
    ):
        return "audio/webm"

    raise ValueError("Unsupported audio format for Prisma v3.0.")


def get_voice_provider(
    modality: Optional[str] = None,
) -> BaseVoiceProvider:

    enabled = settings.GNANI_LIVE_ENABLED and (
        (modality == "stt" and settings.GNANI_PRISMA_ENABLED)
        or (modality == "tts" and settings.GNANI_TIMBRE_ENABLED)
    )

    if enabled:
        return DormantGnaniVoiceProvider()

    return LocalDevelopmentVoiceProvider()


MockGnaniProvider = LocalDevelopmentVoiceProvider
LiveGnaniProvider = DormantGnaniVoiceProvider
