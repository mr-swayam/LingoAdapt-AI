import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.evaluation import DetectedError, DetectedErrorSeverity, DetectedErrorType


def record_detected_error(
    db: Session,
    *,
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    error_type: DetectedErrorType,
    severity: DetectedErrorSeverity,
    description: str,
    submitted_text: str,
    exercise_id: uuid.UUID | None = None,
    conversation_message_id: uuid.UUID | None = None,
) -> DetectedError:
    error = DetectedError(
        user_id=user_id,
        exercise_id=exercise_id,
        conversation_message_id=conversation_message_id,
        skill_id=skill_id,
        error_type=error_type,
        severity=severity,
        description=description,
        submitted_text=submitted_text,
    )
    db.add(error)
    db.flush()
    return error


def list_recent_errors(db: Session, user_id: uuid.UUID, limit: int = 20) -> list[DetectedError]:
    stmt = (
        select(DetectedError)
        .where(DetectedError.user_id == user_id)
        .order_by(DetectedError.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def list_recent_conversation_errors(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int = 0,
    skill_id: uuid.UUID | None = None,
) -> list[DetectedError]:
    """V3.3 Mistake Notebook's TUTOR source - deliberately narrower than
    list_recent_errors above. DetectedError rows aren't exclusively
    tutor-sourced: ai_grading.grade_short_answer also writes rows here (with
    exercise_id set) for SHORT_ANSWER lesson/practice mistakes, which are
    already surfaced as their own LESSON/PRACTICE mistake via
    mistake_repository's ExerciseAttempt/PracticeQuestion queries - including
    them again here under "TUTOR" would both mislabel their source and
    double-count the same underlying mistake. Only rows with
    conversation_message_id set (the AI tutor conversation flow - see
    conversation_service._record_correction) are genuine, non-redundant
    tutor mistakes."""
    stmt = (
        select(DetectedError)
        .where(
            DetectedError.user_id == user_id,
            DetectedError.conversation_message_id.is_not(None),
        )
        .options(joinedload(DetectedError.skill))
        .order_by(DetectedError.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if skill_id is not None:
        stmt = stmt.where(DetectedError.skill_id == skill_id)
    return list(db.execute(stmt).scalars().all())
