"""Provider-agnostic AI gateway (architecture.md §10). The app must never
import a provider SDK directly outside app/ai/ - everything goes through
this interface so the provider can be swapped without touching callers.

`chat()`, `transcribe()`, and `synthesize_speech()` are the I/O primitives.
Higher-level capabilities (EvaluationService, ConversationService, and
Phase 8's speech_service/pronunciation modules) are built on top of them in
app/services/, not baked into the provider itself.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class AIResponse:
    content: str
    latency_ms: int
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    latency_ms: int


@dataclass(frozen=True)
class SpeechResult:
    audio_bytes: bytes
    content_type: str
    latency_ms: int


class AIProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> AIResponse:
        """Raises AITimeoutError / AIRequestError on failure - never returns
        a partial or fabricated response."""
        raise NotImplementedError

    @abstractmethod
    async def transcribe(
        self, audio_bytes: bytes, *, filename: str, content_type: str
    ) -> TranscriptionResult:
        """Speech-to-text (Phase 8). Raises AITimeoutError / AIRequestError
        on failure - never returns a partial or fabricated transcript."""
        raise NotImplementedError

    @abstractmethod
    async def synthesize_speech(self, text: str, *, voice: str) -> SpeechResult:
        """Text-to-speech (Phase 8). Raises AITimeoutError / AIRequestError
        on failure."""
        raise NotImplementedError
