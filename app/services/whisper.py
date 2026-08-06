"""Whisper API wrapper: voice (ogg/opus) bytes -> transcribed text."""
from __future__ import annotations

import io

from openai import AsyncOpenAI

from app.utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


class TranscriptionError(RuntimeError):
    """Raised when Whisper fails to transcribe a voice message."""


async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Send raw audio bytes to Whisper and return the transcribed text.

    Callers should catch TranscriptionError and offer the user a manual
    text-entry fallback (see README troubleshooting: Whisper latency/timeout).
    """
    if not audio_bytes:
        raise TranscriptionError("Empty audio payload")

    client = get_openai_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    try:
        transcript = await client.audio.transcriptions.create(
            model=settings.whisper_model,
            file=audio_file,
        )
    except Exception as exc:  # noqa: BLE001 - surface as a domain error
        logger.warning("whisper_transcription_failed", exc_info=exc)
        raise TranscriptionError(str(exc)) from exc

    text = (transcript.text or "").strip()
    if not text:
        raise TranscriptionError("Whisper returned empty transcription")
    return text
