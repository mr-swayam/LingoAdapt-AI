import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import TZ_DATETIME, Base


class ExerciseType(enum.StrEnum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    FILL_BLANK = "FILL_BLANK"
    TRANSLATION = "TRANSLATION"
    WORD_ORDER = "WORD_ORDER"
    MATCHING = "MATCHING"
    # Free-form written answer, graded by AI (app/services/evaluation_service.py)
    # rather than exact-match (app/services/grading.py handles the rest).
    SHORT_ANSWER = "SHORT_ANSWER"
    # Phase 8: learner speaks a target phrase; graded deterministically by
    # comparing an AI transcript (STT) against correct_answer.answers, same
    # exact-match family as FILL_BLANK/TRANSLATION - only the *input channel*
    # is AI-mediated, not the correctness decision (rules.md §2).
    SPEAKING = "SPEAKING"
    # Phase 8: learner hears synthesized audio (TTS, correct_answer.text_to_speak,
    # kept out of `payload` so it never leaks to the client) and types what they
    # heard - graded identically to FILL_BLANK.
    LISTENING = "LISTENING"


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    courses: Mapped[list["Course"]] = relationship(back_populates="language")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("languages.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )

    language: Mapped["Language"] = relationship(back_populates="courses")
    units: Mapped[list["Unit"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Unit.position"
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="units")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan", order_by="Lesson.position"
    )

    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_unit_course_position"),)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    unit: Mapped["Unit"] = relationship(back_populates="lessons")
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="Exercise.position"
    )

    __table_args__ = (UniqueConstraint("unit_id", "position", name="uq_lesson_unit_position"),)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    course: Mapped["Course"] = relationship(back_populates="skills")

    __table_args__ = (UniqueConstraint("course_id", "code", name="uq_skill_course_code"),)


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False, index=True
    )
    type: Mapped[ExerciseType] = mapped_column(
        Enum(ExerciseType, name="exercise_type", native_enum=True), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    correct_answer: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 0 (easiest) - 1 (hardest). Static content rating for now; Phase 5 adds
    # adaptive difficulty *selection* driven by learner ability, not this field.
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    lesson: Mapped["Lesson"] = relationship(back_populates="exercises")
    skill: Mapped["Skill"] = relationship()
    options: Mapped[list["ExerciseOption"]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        order_by="ExerciseOption.position",
    )

    __table_args__ = (
        UniqueConstraint("lesson_id", "position", name="uq_exercise_lesson_position"),
    )


class ExerciseOption(Base):
    """Discrete selectable/orderable items for an exercise.

    Column meaning depends on the parent exercise's type:
    - MULTIPLE_CHOICE: `text` is the choice label, `is_correct` marks the answer.
    - WORD_ORDER: `text` is one token; `correct_position` is its index in the
      correctly ordered sentence.
    - MATCHING: `text` is one side's item; `match_group` is "left"/"right" and
      options sharing the same `match_key` are the correct pair.
    - FILL_BLANK / TRANSLATION: unused - grading reads `exercises.correct_answer`.
    """

    __tablename__ = "exercise_options"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    correct_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    match_key: Mapped[str | None] = mapped_column(String(50), nullable=True)

    exercise: Mapped["Exercise"] = relationship(back_populates="options")
