import random
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.course import Course, Exercise, ExerciseOption, ExerciseType, Lesson, Unit
from app.models.progress import LessonAttempt, LessonAttemptStatus


class LessonSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    position: int
    exercise_count: int
    # V2 redesign: real per-learner completion, for the /learn path visual.
    # No "locked" state is exposed here - the backend doesn't enforce or
    # track lesson-unlock prerequisites (start_lesson has no such check),
    # so a locked/unlocked visual would be fabricated. Only completed vs.
    # not-completed is real.
    completed: bool = False

    @classmethod
    def from_model(
        cls, lesson: Lesson, *, completed_lesson_ids: frozenset[uuid.UUID] = frozenset()
    ) -> "LessonSummaryOut":
        # Default of "nothing completed" is correct for the callers that
        # don't have a specific learner in view (admin authoring preview,
        # the unauthenticated single-lesson lookup) - only
        # CourseDetailOut.from_model (the learner-facing /courses/{id})
        # passes a real per-user set.
        return cls(
            id=lesson.id,
            title=lesson.title,
            position=lesson.position,
            exercise_count=len(lesson.exercises),
            completed=lesson.id in completed_lesson_ids,
        )


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    position: int
    lessons: list[LessonSummaryOut]

    @classmethod
    def from_model(
        cls, unit: Unit, *, completed_lesson_ids: frozenset[uuid.UUID] = frozenset()
    ) -> "UnitOut":
        return cls(
            id=unit.id,
            title=unit.title,
            position=unit.position,
            lessons=[
                LessonSummaryOut.from_model(lesson, completed_lesson_ids=completed_lesson_ids)
                for lesson in unit.lessons
            ],
        )


class CourseSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    language_code: str
    language_name: str
    unit_count: int
    lesson_count: int

    @classmethod
    def from_model(cls, course: Course) -> "CourseSummaryOut":
        return cls(
            id=course.id,
            title=course.title,
            description=course.description,
            language_code=course.language.code,
            language_name=course.language.name,
            unit_count=len(course.units),
            lesson_count=sum(len(unit.lessons) for unit in course.units),
        )


class CourseDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    language_code: str
    language_name: str
    units: list[UnitOut]

    @classmethod
    def from_model(
        cls, course: Course, *, completed_lesson_ids: frozenset[uuid.UUID] = frozenset()
    ) -> "CourseDetailOut":
        return cls(
            id=course.id,
            title=course.title,
            description=course.description,
            language_code=course.language.code,
            language_name=course.language.name,
            units=[
                UnitOut.from_model(unit, completed_lesson_ids=completed_lesson_ids)
                for unit in course.units
            ],
        )


def _display_order(
    exercise_type: ExerciseType, options: list[ExerciseOption]
) -> list[ExerciseOption]:
    """Options are stored in their correct order/pairing, which would make
    WORD_ORDER and MATCHING trivially solvable if returned as-is (position
    order == correct order). Shuffle a display copy; grading still uses the
    DB-stored correct_position/match_key, never this order."""
    if exercise_type == ExerciseType.WORD_ORDER:
        shuffled = list(options)
        random.shuffle(shuffled)
        return shuffled
    if exercise_type == ExerciseType.MATCHING:
        left = [opt for opt in options if opt.match_group == "left"]
        right = [opt for opt in options if opt.match_group == "right"]
        random.shuffle(right)
        # Interleaved so the API response doesn't itself reveal the grouping order.
        return [opt for pair in zip(left, right, strict=True) for opt in pair]
    return list(options)


class ExerciseOptionPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    match_group: str | None = None


class ExercisePublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: ExerciseType
    prompt: str
    payload: dict[str, Any]
    options: list[ExerciseOptionPublicOut]

    @classmethod
    def from_model(cls, exercise: Exercise) -> "ExercisePublicOut":
        return cls(
            id=exercise.id,
            type=exercise.type,
            prompt=exercise.prompt,
            payload=exercise.payload,
            options=[
                ExerciseOptionPublicOut.model_validate(opt)
                for opt in _display_order(exercise.type, exercise.options)
            ],
        )


class LessonStartResponse(BaseModel):
    lesson_attempt_id: uuid.UUID
    lesson_id: uuid.UUID
    lesson_title: str
    status: LessonAttemptStatus
    total_count: int
    correct_count: int
    answered_exercise_ids: list[uuid.UUID]
    exercises: list[ExercisePublicOut]

    @classmethod
    def build(cls, attempt: LessonAttempt, lesson: Lesson) -> "LessonStartResponse":
        return cls(
            lesson_attempt_id=attempt.id,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            status=attempt.status,
            total_count=attempt.total_count,
            correct_count=attempt.correct_count,
            answered_exercise_ids=[ea.exercise_id for ea in attempt.exercise_attempts],
            exercises=[ExercisePublicOut.from_model(ex) for ex in lesson.exercises],
        )


class AnswerSubmitRequest(BaseModel):
    lesson_attempt_id: uuid.UUID
    submitted_answer: dict[str, Any]


class AnswerResultOut(BaseModel):
    is_correct: bool
    correct_answer: dict[str, Any]
    explanation: str | None
    lesson_completed: bool
    correct_count: int
    total_count: int
    xp_earned: int
    current_streak: int | None
    new_achievements: list[str]


class AudioAnswerResultOut(AnswerResultOut):
    """Same shape as AnswerResultOut, plus the AI-transcribed text so the
    frontend can show the learner what they were heard saying (Phase 8
    SPEAKING exercises)."""

    transcript: str
