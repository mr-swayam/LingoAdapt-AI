import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import TZ_DATETIME, Base


class LessonAttemptStatus(enum.StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class LessonAttempt(Base):
    __tablename__ = "lesson_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[LessonAttemptStatus] = mapped_column(
        Enum(LessonAttemptStatus, name="lesson_attempt_status", native_enum=True),
        nullable=False,
        default=LessonAttemptStatus.IN_PROGRESS,
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Indexed (Phase 12): analytics_repository.get_lesson_completion_stats
    # filters this table by started_at range.
    started_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)

    exercise_attempts: Mapped[list["ExerciseAttempt"]] = relationship(
        back_populates="lesson_attempt", cascade="all, delete-orphan"
    )


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lesson_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lesson_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    submitted_answer: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Stored (not recomputed) so a resubmit of the same exercise never
    # re-invokes grading - free/deterministic for the exact-match types, but
    # AI-graded SHORT_ANSWER grading is a paid, non-deterministic call that
    # must only ever run once per answer (rules.md §2.6: avoid unnecessary
    # AI calls).
    correct_answer: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )

    lesson_attempt: Mapped["LessonAttempt"] = relationship(back_populates="exercise_attempts")

    __table_args__ = (
        UniqueConstraint(
            "lesson_attempt_id", "exercise_id", name="uq_exercise_attempt_per_lesson_attempt"
        ),
    )
