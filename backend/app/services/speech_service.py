"""Thin wrappers over AIProvider.transcribe()/synthesize_speech(), mirroring
evaluation_service.py's role for chat() - callers never talk to the
provider directly.

No object storage in this stack (architecture.md §2 lists it as the
production-recommended approach; out of scope for local dev - see
README's Phase 8 known limitations). Synthesized audio is instead cached
in-memory per process, keyed by the *content* that produced it (an
exercise id, or a conversation message id) - both are immutable once
created, so re-fetching the same key never needs a second AI call.
"""

import uuid

from app.ai.base import AIProvider, SpeechResult
from app.ai.exceptions import AIProviderNotConfiguredError

DEFAULT_VOICE = "daniel"

# Generous for a single spoken sentence (typically well under 1MB) while
# still bounding request size at this boundary, before it ever reaches the
# AI provider.
MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Unbounded for this MVP's scale (one seed course, single-process dev
# server) - a production deployment would swap this for a real cache/CDN
# in front of object storage, not grow this dict forever.
_speech_cache: dict[str, SpeechResult] = {}


class AudioTooLargeError(Exception):
    pass


def validate_audio_size(audio_bytes: bytes) -> None:
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise AudioTooLargeError(len(audio_bytes))


async def transcribe_audio(
    provider: AIProvider | None, audio_bytes: bytes, *, filename: str, content_type: str
) -> str:
    if provider is None:
        raise AIProviderNotConfiguredError
    result = await provider.transcribe(audio_bytes, filename=filename, content_type=content_type)
    return result.text.strip()


async def synthesize_cached(
    provider: AIProvider | None,
    *,
    cache_key: str,
    text: str,
    voice: str = DEFAULT_VOICE,
) -> SpeechResult:
    if provider is None:
        raise AIProviderNotConfiguredError
    cached = _speech_cache.get(cache_key)
    if cached is not None:
        return cached
    result = await provider.synthesize_speech(text, voice=voice)
    _speech_cache[cache_key] = result
    return result


def exercise_audio_cache_key(exercise_id: uuid.UUID) -> str:
    return f"exercise:{exercise_id}"


def message_audio_cache_key(message_id: uuid.UUID) -> str:
    return f"message:{message_id}"
