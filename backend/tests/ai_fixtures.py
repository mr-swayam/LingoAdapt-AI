"""A deterministic, mocked AI provider so the test suite never needs a live
AI API key or network access (rules.md: "create deterministic mocked
provider tests so the test suite does not require a live AI API").
"""

import json

from app.ai.base import AIProvider, AIResponse, ChatMessage, SpeechResult, TranscriptionResult
from app.ai.exceptions import AIRequestError, AITimeoutError


class FakeAIProvider(AIProvider):
    """Returns a pre-programmed response (or raises a pre-programmed
    failure) regardless of what's asked - tests control behavior via
    `next_response` / `next_error` rather than real model output.
    """

    def __init__(self) -> None:
        self.next_response: dict | None = None
        self.next_error: Exception | None = None
        self.next_transcription: str | None = None
        self.next_speech: SpeechResult | None = None
        self.calls: list[list[ChatMessage]] = []
        self.transcribe_calls: list[tuple[str, str]] = []
        self.synthesize_calls: list[tuple[str, str]] = []

    def queue_evaluation(
        self,
        *,
        is_correct: bool,
        score: float,
        explanation: str = "Looks good.",
        corrected_answer: str = "",
        errors: list[dict] | None = None,
    ) -> None:
        self.next_response = {
            "is_correct": is_correct,
            "score": score,
            "errors": errors or [],
            "explanation": explanation,
            "corrected_answer": corrected_answer,
        }

    def queue_conversation_turn(
        self, *, reply: str, corrections: list[dict] | None = None
    ) -> None:
        self.next_response = {"reply": reply, "corrections": corrections or []}

    def queue_transcription(self, text: str) -> None:
        self.next_transcription = text

    def queue_speech(
        self, *, audio_bytes: bytes = b"fake-wav-bytes", content_type: str = "audio/wav"
    ) -> None:
        self.next_speech = SpeechResult(
            audio_bytes=audio_bytes, content_type=content_type, latency_ms=5
        )

    def queue_timeout(self) -> None:
        self.next_error = AITimeoutError("simulated timeout")

    def queue_request_error(self) -> None:
        self.next_error = AIRequestError("simulated provider failure")

    def queue_raw_content(self, content: str) -> None:
        """For testing schema-validation failures with malformed JSON."""
        self._raw_override = content
        self.next_response = {}

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> AIResponse:
        self.calls.append(messages)

        if self.next_error is not None:
            error = self.next_error
            self.next_error = None
            raise error

        content = getattr(self, "_raw_override", None) or json.dumps(self.next_response or {})
        if hasattr(self, "_raw_override"):
            del self._raw_override

        return AIResponse(content=content, latency_ms=5, model="fake-model")

    async def transcribe(
        self, audio_bytes: bytes, *, filename: str, content_type: str
    ) -> TranscriptionResult:
        self.transcribe_calls.append((filename, content_type))

        if self.next_error is not None:
            error = self.next_error
            self.next_error = None
            raise error

        return TranscriptionResult(text=self.next_transcription or "", latency_ms=5)

    async def synthesize_speech(self, text: str, *, voice: str) -> SpeechResult:
        self.synthesize_calls.append((text, voice))

        if self.next_error is not None:
            error = self.next_error
            self.next_error = None
            raise error

        return self.next_speech or SpeechResult(
            audio_bytes=b"fake-wav-bytes", content_type="audio/wav", latency_ms=5
        )
