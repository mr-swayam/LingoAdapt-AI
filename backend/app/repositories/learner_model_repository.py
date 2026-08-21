import uuid
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.learner_model import LearningEvent, LearningEventType, SkillMastery


def create_learning_event(
    db: Session,
    *,
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    event_type: LearningEventType,
    is_correct: bool,
    difficulty: float,
    exercise_id: uuid.UUID | None = None,
    conversation_message_id: uuid.UUID | None = None,
    response_time_ms: int | None = None,
) -> LearningEvent:
    event = LearningEvent(
        user_id=user_id,
        exercise_id=exercise_id,
        conversation_message_id=conversation_message_id,
        skill_id=skill_id,
        event_type=event_type,
        is_correct=is_correct,
        difficulty=difficulty,
        response_time_ms=response_time_ms,
    )
    db.add(event)
    db.flush()
    return event


def get_skill_mastery(
    db: Session, *, user_id: uuid.UUID, skill_id: uuid.UUID
) -> SkillMastery | None:
    return db.get(SkillMastery, (user_id, skill_id))


def save_skill_mastery(
    db: Session,
    *,
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    mastery: float,
    confidence: float,
    attempt_count: int,
    correct_count: int,
    last_practiced_at: datetime,
    next_review_at: datetime,
    ease_factor: float,
    repetitions: int,
    interval_days: int,
) -> SkillMastery:
    row = get_skill_mastery(db, user_id=user_id, skill_id=skill_id)
    if row is None:
        row = SkillMastery(user_id=user_id, skill_id=skill_id)
        db.add(row)
    row.mastery = mastery
    row.confidence = confidence
    row.attempt_count = attempt_count
    row.correct_count = correct_count
    row.last_practiced_at = last_practiced_at
    row.next_review_at = next_review_at
    row.ease_factor = ease_factor
    row.repetitions = repetitions
    row.interval_days = interval_days
    db.flush()
    return row


def list_skill_mastery_for_user(db: Session, user_id: uuid.UUID) -> list[SkillMastery]:
    stmt = (
        select(SkillMastery)
        .where(SkillMastery.user_id == user_id)
        .options(joinedload(SkillMastery.skill))
    )
    return list(db.execute(stmt).scalars().all())


def list_due_for_review(db: Session, *, user_id: uuid.UUID, now: datetime) -> list[SkillMastery]:
    stmt = (
        select(SkillMastery)
        .where(SkillMastery.user_id == user_id, SkillMastery.next_review_at <= now)
        .options(joinedload(SkillMastery.skill))
        .order_by(SkillMastery.next_review_at)
    )
    return list(db.execute(stmt).scalars().all())


def count_recent_incorrect(
    db: Session, *, user_id: uuid.UUID, skill_id: uuid.UUID, window: int = 5
) -> int:
    """How many of the learner's last `window` answers on this skill were
    wrong - feeds the recommendation engine's recent_mistakes term.
    """
    recent_ids_subquery = (
        select(LearningEvent.id)
        .where(LearningEvent.user_id == user_id, LearningEvent.skill_id == skill_id)
        .order_by(LearningEvent.created_at.desc())
        .limit(window)
        .subquery()
    )
    stmt = select(func.count()).where(
        LearningEvent.id.in_(select(recent_ids_subquery.c.id)),
        LearningEvent.is_correct.is_(False),
    )
    return int(db.execute(stmt).scalar_one())


def get_skill_accuracy_in_window(
    db: Session, *, user_id: uuid.UUID, skill_id: uuid.UUID, start: datetime, end: datetime
) -> tuple[int, int]:
    """(correct_count, total_count) among this user's LearningEvents for one
    skill in [start, end) - the per-skill windowed building block for
    learner_insight_service.get_improving_skills's recent-vs-previous
    accuracy comparison (V3.1/V3.2). Same explicit-bounds style as
    analytics_repository's _utc_day_bounds queries, not func.date(...)."""
    stmt = select(
        func.count(),
        func.sum(case((LearningEvent.is_correct.is_(True), 1), else_=0)),
    ).where(
        LearningEvent.user_id == user_id,
        LearningEvent.skill_id == skill_id,
        LearningEvent.created_at >= start,
        LearningEvent.created_at < end,
    )
    total, correct = db.execute(stmt).one()
    return int(correct or 0), int(total or 0)


def get_missed_exercise_ids(
    db: Session, *, user_id: uuid.UUID, skill_id: uuid.UUID
) -> set[uuid.UUID]:
    """Exercises this user has ever gotten wrong for this skill, drawn from
    the unified learning_events log (covers both lesson and practice
    answers) - feeds practice exercise selection's "mistake review" bias.
    """
    stmt = (
        select(LearningEvent.exercise_id)
        .where(
            LearningEvent.user_id == user_id,
            LearningEvent.skill_id == skill_id,
            LearningEvent.is_correct.is_(False),
            LearningEvent.exercise_id.is_not(None),
        )
        .distinct()
    )
    return {row for row in db.execute(stmt).scalars().all() if row is not None}
