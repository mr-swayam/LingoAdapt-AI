import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TZ_DATETIME, Base


class AiCallOperation(enum.StrEnum):
    CHAT = "CHAT"
    TRANSCRIBE = "TRANSCRIBE"
    SPEECH = "SPEECH"


class AiCallLog(Base):
    """One row per AIProvider call (app/ai/metering.py wraps every provider
    handed to a request-scoped call site), feeding Phase 11's AI latency /
    error-rate metrics. Deliberately a plain append-only log, not something
    business logic reads - callers never branch on this table, matching
    rules.md's "AI failure must not corrupt learning state" (this table is
    pure observability, isolated from every learner-state transaction).
    """

    __tablename__ = "ai_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Nullable: a call whose owning user can't be resolved (there are none
    # today - every AI call site requires an authenticated user - but this
    # keeps the log itself from ever blocking on a stricter constraint).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation: Mapped[AiCallOperation] = mapped_column(
        Enum(AiCallOperation, name="ai_call_operation", native_enum=True),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    # Exception class name (e.g. "AITimeoutError") - enough to break down
    # error rate by failure mode without persisting free-form provider text.
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False, index=True
    )
