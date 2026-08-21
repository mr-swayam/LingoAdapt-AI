"""Raw per-attempt wrong-answer queries (V3.3 Mistake Notebook). Nothing
here is a new table - ExerciseAttempt and PracticeQuestion already store
the learner's submitted answer, the correct answer, and a timestamp per
attempt (confirmed in V3_ADAPTIVE_INTELLIGENCE_AUDIT.md §4.3); this module
just queries that existing data for a learner-facing view for the first
time.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.course import Exercise, ExerciseType
from app.models.practice import PracticeQuestion, PracticeSession
from app.models.progress import ExerciseAttempt, LessonAttempt


def list_wrong_exercise_attempts(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int = 0,
    skill_id: uuid.UUID | None = None,
    exercise_type: ExerciseType | None = None,
) -> list[ExerciseAttempt]:
    """Wrong lesson-exercise attempts for this user, newest first. Filters
    are applied as real SQL predicates (not post-filtered in Python) so
    mistake_service's offset+limit-per-source pagination fetch stays
    correct - see mistake_service.list_mistakes for why."""
    stmt = (
        select(ExerciseAttempt)
        .join(LessonAttempt, ExerciseAttempt.lesson_attempt_id == LessonAttempt.id)
        .join(Exercise, ExerciseAttempt.exercise_id == Exercise.id)
        .where(LessonAttempt.user_id == user_id, ExerciseAttempt.is_correct.is_(False))
        .options(joinedload(ExerciseAttempt.exercise).joinedload(Exercise.skill))
        .order_by(ExerciseAttempt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if skill_id is not None:
        stmt = stmt.where(Exercise.skill_id == skill_id)
    if exercise_type is not None:
        stmt = stmt.where(Exercise.type == exercise_type)
    return list(db.execute(stmt).scalars().unique().all())


def list_wrong_practice_questions(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int = 0,
    skill_id: uuid.UUID | None = None,
    exercise_type: ExerciseType | None = None,
) -> list[PracticeQuestion]:
    """Wrong, answered practice questions for this user, newest first.
    `answered_at` (not `created_at`, which PracticeQuestion doesn't have -
    a question row exists from selection time, before it's answered) is the
    ordering/recency basis, matching what the learner actually experienced
    as "when I got this wrong"."""
    stmt = (
        select(PracticeQuestion)
        .join(PracticeSession, PracticeQuestion.practice_session_id == PracticeSession.id)
        .join(Exercise, PracticeQuestion.exercise_id == Exercise.id)
        .where(
            PracticeSession.user_id == user_id,
            PracticeQuestion.is_correct.is_(False),
            PracticeQuestion.answered_at.is_not(None),
        )
        .options(joinedload(PracticeQuestion.exercise).joinedload(Exercise.skill))
        .order_by(PracticeQuestion.answered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if skill_id is not None:
        stmt = stmt.where(Exercise.skill_id == skill_id)
    if exercise_type is not None:
        stmt = stmt.where(Exercise.type == exercise_type)
    return list(db.execute(stmt).scalars().unique().all())


def exercise_id_is_a_past_mistake(
    db: Session, *, user_id: uuid.UUID, exercise_id: uuid.UUID
) -> bool:
    """Ownership check for "Retry this exercise" (V3 architecture review
    item 17): a client-supplied exercise_id must genuinely be one of this
    user's own wrong attempts (lesson or practice) before it can be used to
    build a targeted practice session - otherwise a client could hand-pick
    arbitrary exercises into a session that's supposed to be a real mistake
    retry."""
    lesson_stmt = (
        select(ExerciseAttempt.id)
        .join(LessonAttempt, ExerciseAttempt.lesson_attempt_id == LessonAttempt.id)
        .where(
            LessonAttempt.user_id == user_id,
            ExerciseAttempt.exercise_id == exercise_id,
            ExerciseAttempt.is_correct.is_(False),
        )
        .limit(1)
    )
    if db.execute(lesson_stmt).first() is not None:
        return True

    practice_stmt = (
        select(PracticeQuestion.id)
        .join(PracticeSession, PracticeQuestion.practice_session_id == PracticeSession.id)
        .where(
            PracticeSession.user_id == user_id,
            PracticeQuestion.exercise_id == exercise_id,
            PracticeQuestion.is_correct.is_(False),
        )
        .limit(1)
    )
    return db.execute(practice_stmt).first() is not None
