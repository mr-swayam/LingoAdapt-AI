import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import TZ_DATETIME, Base
from app.models.course import Skill  # noqa: F401 - referenced by string in relationship()


class LearningEventType(enum.StrEnum):
    ANSWER_SUBMITTED = "ANSWER_SUBMITTED"
    CONVERSATION_CORRECTION = "CONVERSATION_CORRECTION"


class LearningEvent(Base):
    """Append-only log of meaningful learning actions (architecture.md §7).
    Consumed by the learner model to update skill_mastery; never mutated.

    Exactly one of exercise_id / conversation_message_id is set, matching
    event_type - ANSWER_SUBMITTED events come from exercises (lessons or
    practice), CONVERSATION_CORRECTION events come from the AI tutor
    (rules.md §6.8: "remember relevant conversation mistakes through
    learning events").
    """

    __tablename__ = "learning_events"

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
    event_type: Mapped[LearningEventType] = mapped_column(
        Enum(LearningEventType, name="learning_event_type", native_enum=True), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False)
    # Optional - not yet captured by the frontend (no exercise-start timing
    # instrumentation exists). Column is ready for when that lands.
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Indexed (Phase 12): app/repositories/analytics_repository.py filters
    # this table by created_at range for every daily-active-user/retention/
    # improvement-trend query.
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "(exercise_id IS NOT NULL)::int + (conversation_message_id IS NOT NULL)::int = 1",
            name="ck_learning_event_exactly_one_source",
        ),
    )


class SkillMastery(Base):
    """One row per (user, skill). Updated after every learning event for
    that skill via a bounded, isolated formula (app/services/mastery.py) -
    never mutated directly by anything else, per rules.md §3.
    """

    __tablename__ = "skill_mastery"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_practiced_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)
    # Simplified SM-2 style spaced repetition (memory.md §9: interval, ease,
    # repetitions, last_reviewed, next_review). Computed by
    # app/services/spaced_repetition.py, which replaces Phase 4's flat
    # mastery-bucket next_review_at with a real per-skill schedule.
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    skill: Mapped["Skill"] = relationship()

    __table_args__ = (
        CheckConstraint("mastery >= 0 AND mastery <= 100", name="ck_skill_mastery_bounded"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 100", name="ck_skill_confidence_bounded"
        ),
        CheckConstraint("ease_factor >= 1.3", name="ck_skill_ease_factor_floor"),
    )
