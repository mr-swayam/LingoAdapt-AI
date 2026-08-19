import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TZ_DATETIME, Base


class DetectedErrorType(enum.StrEnum):
    GRAMMAR = "GRAMMAR"
    VOCABULARY = "VOCABULARY"
    SPELLING = "SPELLING"
    WORD_ORDER = "WORD_ORDER"
    OTHER = "OTHER"


class DetectedErrorSeverity(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DetectedError(Base):
    """AI-classified errors from free-form answer evaluation (Phase 6) or
    AI tutor conversation corrections (Phase 7). Deterministic exercise
    types (multiple choice, fill-blank, etc.) never produce rows here -
    their grading is exact-match, there's nothing to classify beyond
    right/wrong.

    Exactly one of exercise_id / conversation_message_id is set.
    """

    __tablename__ = "detected_errors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=True
    )
    conversation_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    error_type: Mapped[DetectedErrorType] = mapped_column(
        Enum(DetectedErrorType, name="detected_error_type", native_enum=True), nullable=False
    )
    severity: Mapped[DetectedErrorSeverity] = mapped_column(
        Enum(DetectedErrorSeverity, name="detected_error_severity", native_enum=True),
        nullable=False,
    )
    # The AI's "skill" field: a short human-readable description of what
    # went wrong (e.g. "missing verb 'am'"), distinct from Skill.id which
    # identifies the language-learning skill being practiced.
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Indexed (Phase 12): analytics_repository.get_top_mistake_types filters
    # this table by created_at range.
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "(exercise_id IS NOT NULL)::int + (conversation_message_id IS NOT NULL)::int = 1",
            name="ck_detected_error_exactly_one_source",
        ),
    )
