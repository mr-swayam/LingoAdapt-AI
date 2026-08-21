import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.models.course import ExerciseType, Lesson
from app.models.progress import ExerciseAttempt, LessonAttempt, LessonAttemptStatus
from app.repositories import course_repository, progress_repository
from app.services import ai_grading, coach_service, gamification_service, learner_model_service
from app.services.grading import grade_exercise


class LessonServiceError(Exception):
    pass


class LessonNotFoundError(LessonServiceError):
    pass


class AttemptNotFoundError(LessonServiceError):
    pass


class AttemptNotOwnedError(LessonServiceError):
    pass


class AttemptAlreadyCompletedError(LessonServiceError):
    pass


class ExerciseNotInAttemptError(LessonServiceError):
    pass


def start_lesson(
    db: Session, *, user_id: uuid.UUID, lesson_id: uuid.UUID
) -> tuple[LessonAttempt, Lesson]:
    lesson = course_repository.get_lesson(db, lesson_id)
    if lesson is None:
        raise LessonNotFoundError(lesson_id)

    attempt = progress_repository.get_in_progress_attempt(
        db, user_id=user_id, lesson_id=lesson_id
    )
    if attempt is None:
        attempt = progress_repository.create_attempt(
            db, user_id=user_id, lesson_id=lesson_id, total_count=len(lesson.exercises)
        )
        db.commit()

    return attempt, lesson


def get_existing_answer(
    db: Session, *, user_id: uuid.UUID, exercise_id: uuid.UUID, lesson_attempt_id: uuid.UUID
) -> ExerciseAttempt | None:
    """Read-only idempotency pre-check for callers that must do expensive
    work (Phase 8: transcribing audio) *before* they have a submitted_answer
    to hand to submit_answer(). Lets them skip that work entirely when the
    exercise was already answered, instead of paying for it and then
    discarding the result once submit_answer's own idempotency check
    (further down this file) ignores it anyway.
    """
    attempt = progress_repository.get_attempt(db, lesson_attempt_id)
    if attempt is None:
        raise AttemptNotFoundError(lesson_attempt_id)
    if attempt.user_id != user_id:
        raise AttemptNotOwnedError(lesson_attempt_id)
    return progress_repository.get_exercise_attempt(
        db, lesson_attempt_id=attempt.id, exercise_id=exercise_id
    )


@dataclass(frozen=True)
class SubmitAnswerResult:
    is_correct: bool
    correct_answer: dict
    explanation: str | None
    lesson_completed: bool
    correct_count: int
    total_count: int
    xp_earned: int
    current_streak: int | None
    new_achievement_codes: list[str]


async def submit_answer(
    db: Session,
    *,
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    lesson_attempt_id: uuid.UUID,
    submitted_answer: dict,
    ai_provider: AIProvider | None = None,
) -> SubmitAnswerResult:
    attempt = progress_repository.get_attempt(db, lesson_attempt_id)
    if attempt is None:
        raise AttemptNotFoundError(lesson_attempt_id)
    if attempt.user_id != user_id:
        raise AttemptNotOwnedError(lesson_attempt_id)
    if attempt.status != LessonAttemptStatus.IN_PROGRESS:
        raise AttemptAlreadyCompletedError(lesson_attempt_id)

    exercise = course_repository.get_exercise(db, exercise_id)
    if exercise is None or exercise.lesson_id != attempt.lesson_id:
        raise ExerciseNotInAttemptError(exercise_id)

    existing = progress_repository.get_exercise_attempt(
        db, lesson_attempt_id=attempt.id, exercise_id=exercise.id
    )
    if existing is not None:
        # Idempotent resubmission (e.g. a retried request): return the
        # already-recorded result. Never recompute - for SHORT_ANSWER that
        # would mean a second paid, non-deterministic AI call for the same
        # answer.
        is_correct, correct_answer, explanation = (
            existing.is_correct,
            existing.correct_answer,
            existing.explanation,
        )
    else:
        if exercise.type == ExerciseType.SHORT_ANSWER:
            submitted_text = submitted_answer.get("text", "")
            is_correct, correct_answer, explanation = await ai_grading.grade_short_answer(
                db,
                ai_provider,
                user_id=user_id,
                exercise=exercise,
                submitted_text=submitted_text,
            )
        else:
            is_correct, correct_answer = grade_exercise(exercise, submitted_answer)
            explanation = exercise.explanation

        progress_repository.record_exercise_attempt(
            db,
            lesson_attempt_id=attempt.id,
            exercise_id=exercise.id,
            submitted_answer=submitted_answer,
            is_correct=is_correct,
            correct_answer=correct_answer,
            explanation=explanation,
        )
        if is_correct:
            attempt.correct_count += 1

        learner_model_service.record_answer_learning_event(
            db, user_id=user_id, exercise=exercise, is_correct=is_correct
        )

        answered_count = len(attempt.exercise_attempts) + 1
        if answered_count >= attempt.total_count:
            attempt.status = LessonAttemptStatus.COMPLETED
            attempt.completed_at = datetime.now(UTC)
            # V3.1 Coach cache invalidation (architecture review item 14):
            # a lesson completing is one of this app's two real "meaningful
            # activity" checkpoints - see coach_service.invalidate_coach_
            # cache's docstring for why this granularity (not per-answer)
            # was chosen.
            coach_service.invalidate_coach_cache(user_id)

    lesson_completed = attempt.status == LessonAttemptStatus.COMPLETED

    xp_earned = 0
    current_streak: int | None = None
    new_achievement_codes: list[str] = []
    if lesson_completed:
        rewards = gamification_service.apply_lesson_completion_rewards(
            db, user_id=user_id, attempt=attempt
        )
        xp_earned = rewards.xp_earned
        current_streak = rewards.current_streak
        new_achievement_codes = [a.code for a in rewards.new_achievements]

    db.commit()

    return SubmitAnswerResult(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=explanation,
        lesson_completed=lesson_completed,
        correct_count=attempt.correct_count,
        total_count=attempt.total_count,
        xp_earned=xp_earned,
        current_streak=current_streak,
        new_achievement_codes=new_achievement_codes,
    )
