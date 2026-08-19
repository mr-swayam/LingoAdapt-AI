import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.progress import ExerciseAttempt, LessonAttempt, LessonAttemptStatus


def get_in_progress_attempt(
    db: Session, *, user_id: uuid.UUID, lesson_id: uuid.UUID
) -> LessonAttempt | None:
    stmt = (
        select(LessonAttempt)
        .where(
            LessonAttempt.user_id == user_id,
            LessonAttempt.lesson_id == lesson_id,
            LessonAttempt.status == LessonAttemptStatus.IN_PROGRESS,
        )
        .options(selectinload(LessonAttempt.exercise_attempts))
    )
    return db.execute(stmt).scalar_one_or_none()


def get_attempt(db: Session, attempt_id: uuid.UUID) -> LessonAttempt | None:
    stmt = (
        select(LessonAttempt)
        .where(LessonAttempt.id == attempt_id)
        .options(selectinload(LessonAttempt.exercise_attempts))
    )
    return db.execute(stmt).scalar_one_or_none()


def create_attempt(
    db: Session, *, user_id: uuid.UUID, lesson_id: uuid.UUID, total_count: int
) -> LessonAttempt:
    attempt = LessonAttempt(user_id=user_id, lesson_id=lesson_id, total_count=total_count)
    db.add(attempt)
    db.flush()
    return attempt


def get_exercise_attempt(
    db: Session, *, lesson_attempt_id: uuid.UUID, exercise_id: uuid.UUID
) -> ExerciseAttempt | None:
    stmt = select(ExerciseAttempt).where(
        ExerciseAttempt.lesson_attempt_id == lesson_attempt_id,
        ExerciseAttempt.exercise_id == exercise_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def record_exercise_attempt(
    db: Session,
    *,
    lesson_attempt_id: uuid.UUID,
    exercise_id: uuid.UUID,
    submitted_answer: dict,
    is_correct: bool,
    correct_answer: dict,
    explanation: str | None,
) -> ExerciseAttempt:
    attempt = ExerciseAttempt(
        lesson_attempt_id=lesson_attempt_id,
        exercise_id=exercise_id,
        submitted_answer=submitted_answer,
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=explanation,
    )
    db.add(attempt)
    db.flush()
    return attempt
