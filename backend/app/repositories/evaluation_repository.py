import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
