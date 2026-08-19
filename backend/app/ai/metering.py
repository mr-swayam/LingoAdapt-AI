"""Wraps any AIProvider to record every call's latency and success/failure
to ai_call_logs (Phase 11's AI latency / error-rate metrics) without
touching the call sites that use AIProvider - they stay exactly as
provider-agnostic and testable as before (architecture.md §10: everything
goes through the AIProvider interface).
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIResponse, ChatMessage, SpeechResult, TranscriptionResult
from app.ai.exceptions import AIProviderError
from app.models.analytics import AiCallOperation
from app.repositories import analytics_repository

logger = logging.getLogger("app.ai")

_T = TypeVar("_T", AIResponse, TranscriptionResult, SpeechResult)


class MeteredAIProvider(AIProvider):
    def __init__(
        self, inner: AIProvider, *, db: Session, user_id: uuid.UUID, provider_name: str
    ) -> None:
        self._inner = inner
        self._db = db
        self._user_id = user_id
        self._provider_name = provider_name

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> AIResponse:
        return await self._call(
            AiCallOperation.CHAT,
            lambda: self._inner.chat(
                messages, json_mode=json_mode, max_tokens=max_tokens, temperature=temperature
            ),
        )

    async def transcribe(
        self, audio_bytes: bytes, *, filename: str, content_type: str
    ) -> TranscriptionResult:
        return await self._call(
            AiCallOperation.TRANSCRIBE,
            lambda: self._inner.transcribe(
                audio_bytes, filename=filename, content_type=content_type
            ),
        )

    async def synthesize_speech(self, text: str, *, voice: str) -> SpeechResult:
        return await self._call(
            AiCallOperation.SPEECH, lambda: self._inner.synthesize_speech(text, voice=voice)
        )

    async def _call(
        self, operation: AiCallOperation, fn: Callable[[], Awaitable[_T]]
    ) -> _T:
        start = time.monotonic()
        try:
            result = await fn()
        except AIProviderError as exc:
            self._record(
                operation,
                latency_ms=int((time.monotonic() - start) * 1000),
                model=None,
                success=False,
                error_type=type(exc).__name__,
            )
            raise
        self._record(
            operation,
            latency_ms=result.latency_ms,
            model=getattr(result, "model", None),
            success=True,
            error_type=None,
        )
        return result

    def _record(
        self,
        operation: AiCallOperation,
        *,
        latency_ms: int,
        model: str | None,
        success: bool,
        error_type: str | None,
    ) -> None:
        # Committed immediately rather than flushed: every current call
        # site invokes the AI provider before writing any learner state
        # (rules.md - "AI failure must not corrupt learning state"; see
        # conversation_service.send_message's comment for the same
        # invariant), so nothing else is pending on this session yet. A
        # metrics-write failure must never break the actual AI feature, so
        # it's caught and swallowed rather than propagated.
        try:
            analytics_repository.record_ai_call(
                self._db,
                user_id=self._user_id,
                operation=operation,
                provider=self._provider_name,
                model=model,
                latency_ms=latency_ms,
                success=success,
                error_type=error_type,
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            logger.exception("ai_call_log_write_failed operation=%s", operation)
