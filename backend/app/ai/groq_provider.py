import logging
import time

import httpx

from app.ai.base import AIProvider, AIResponse, ChatMessage, SpeechResult, TranscriptionResult
from app.ai.exceptions import AIRequestError, AITimeoutError

logger = logging.getLogger("app.ai")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
REQUEST_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS = 2  # one retry on transient (5xx/timeout) failures only

TRANSCRIPTION_MODEL = "whisper-large-v3-turbo"
SPEECH_MODEL = "canopylabs/orpheus-v1-english"
# Orpheus hard-rejects input over 200 characters (Groq's documented limit) -
# truncate at a word boundary so a long conversational reply still gets
# *some* audio rather than a 400 from the provider.
SPEECH_MAX_INPUT_CHARS = 200


class GroqAIProvider(AIProvider):
    def __init__(self, *, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> AIResponse:
        payload: dict = {
            "model": self._default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        f"{GROQ_BASE_URL}/chat/completions",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=payload,
                    )
                latency_ms = int((time.monotonic() - start) * 1000)

                if response.status_code >= 500 and attempt < MAX_ATTEMPTS:
                    logger.warning(
                        "groq_transient_error status=%s attempt=%s", response.status_code, attempt
                    )
                    continue
                if response.status_code != 200:
                    raise AIRequestError(
                        f"Groq returned {response.status_code}: {response.text[:500]}"
                    )

                data = response.json()
                choice = data["choices"][0]["message"]
                usage = data.get("usage", {})
                logger.info(
                    "groq_chat_completed model=%s latency_ms=%s prompt_tokens=%s "
                    "completion_tokens=%s",
                    self._default_model,
                    latency_ms,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                )
                return AIResponse(
                    content=choice["content"],
                    latency_ms=latency_ms,
                    model=data.get("model", self._default_model),
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("groq_timeout attempt=%s", attempt)
                if attempt >= MAX_ATTEMPTS:
                    raise AITimeoutError("Groq request timed out") from exc
            except httpx.HTTPError as exc:
                raise AIRequestError(f"Groq request failed: {exc}") from exc

        # Only reachable if every attempt hit the 5xx-retry branch above.
        raise AIRequestError(f"Groq request failed after {MAX_ATTEMPTS} attempts: {last_error}")

    async def transcribe(
        self, audio_bytes: bytes, *, filename: str, content_type: str
    ) -> TranscriptionResult:
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        f"{GROQ_BASE_URL}/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        data={"model": TRANSCRIPTION_MODEL, "response_format": "json"},
                        files={"file": (filename, audio_bytes, content_type)},
                    )
                latency_ms = int((time.monotonic() - start) * 1000)

                if response.status_code >= 500 and attempt < MAX_ATTEMPTS:
                    logger.warning(
                        "groq_transcribe_transient_error status=%s attempt=%s",
                        response.status_code,
                        attempt,
                    )
                    continue
                if response.status_code != 200:
                    raise AIRequestError(
                        f"Groq transcription returned {response.status_code}: "
                        f"{response.text[:500]}"
                    )

                data = response.json()
                logger.info(
                    "groq_transcribe_completed model=%s latency_ms=%s", TRANSCRIPTION_MODEL,
                    latency_ms,
                )
                return TranscriptionResult(text=data.get("text", ""), latency_ms=latency_ms)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("groq_transcribe_timeout attempt=%s", attempt)
                if attempt >= MAX_ATTEMPTS:
                    raise AITimeoutError("Groq transcription request timed out") from exc
            except httpx.HTTPError as exc:
                raise AIRequestError(f"Groq transcription request failed: {exc}") from exc

        raise AIRequestError(
            f"Groq transcription failed after {MAX_ATTEMPTS} attempts: {last_error}"
        )

    async def synthesize_speech(self, text: str, *, voice: str) -> SpeechResult:
        truncated = text[:SPEECH_MAX_INPUT_CHARS]
        if len(truncated) < len(text):
            # Truncate at the last whole word rather than mid-word.
            truncated = truncated.rsplit(" ", 1)[0] if " " in truncated else truncated

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        f"{GROQ_BASE_URL}/audio/speech",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json={
                            "model": SPEECH_MODEL,
                            "input": truncated,
                            "voice": voice,
                            "response_format": "wav",
                        },
                    )
                latency_ms = int((time.monotonic() - start) * 1000)

                if response.status_code >= 500 and attempt < MAX_ATTEMPTS:
                    logger.warning(
                        "groq_speech_transient_error status=%s attempt=%s",
                        response.status_code,
                        attempt,
                    )
                    continue
                if response.status_code != 200:
                    raise AIRequestError(
                        f"Groq speech synthesis returned {response.status_code}: "
                        f"{response.text[:500]}"
                    )

                logger.info(
                    "groq_speech_completed model=%s voice=%s latency_ms=%s chars=%s",
                    SPEECH_MODEL,
                    voice,
                    latency_ms,
                    len(truncated),
                )
                return SpeechResult(
                    audio_bytes=response.content,
                    content_type=response.headers.get("content-type", "audio/wav"),
                    latency_ms=latency_ms,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("groq_speech_timeout attempt=%s", attempt)
                if attempt >= MAX_ATTEMPTS:
                    raise AITimeoutError("Groq speech synthesis request timed out") from exc
            except httpx.HTTPError as exc:
                raise AIRequestError(f"Groq speech synthesis request failed: {exc}") from exc

        raise AIRequestError(
            f"Groq speech synthesis failed after {MAX_ATTEMPTS} attempts: {last_error}"
        )
