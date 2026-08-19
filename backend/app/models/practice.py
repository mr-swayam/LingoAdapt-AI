import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import TZ_DATETIME, Base


class PracticeSessionStatus(enum.StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class PracticeSession(Base):
    """A personalized, cross-lesson set of exercises selected by the
    recommendation engine (app/services/recommendation.py) - distinct from a
    LessonAttempt, which always works through one lesson's fixed exercise
    list in order.
    """

    __tablename__ = "practice_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[PracticeSessionStatus] = mapped_column(
        Enum(PracticeSessionStatus, name="practice_session_status", native_enum=True),
        nullable=False,
        default=PracticeSessionStatus.IN_PROGRESS,
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Indexed (Phase 12): analytics_repository.get_practice_completion_stats
    # filters this table by started_at range.
    started_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)

    questions: Mapped[list["PracticeQuestion"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class PracticeQuestion(Base):
    """One exercise selected into a practice session, plus the learner's
    answer once submitted. `position` is fixed at selection time so the
    frontend can render a stable, resumable ordering.
    """

    __tablename__ = "practice_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    practice_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # See ExerciseAttempt's matching comment - stored, not recomputed, so a
    # resubmit never re-invokes (paid, non-deterministic) AI grading.
    correct_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)

    session: Mapped["PracticeSession"] = relationship(back_populates="questions")

    __table_args__ = (
        UniqueConstraint(
            "practice_session_id", "exercise_id", name="uq_practice_question_session_exercise"
        ),
    )
