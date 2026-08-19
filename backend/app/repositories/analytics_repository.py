import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.analytics import AiCallLog, AiCallOperation
from app.models.course import Skill
from app.models.evaluation import DetectedError, DetectedErrorType
from app.models.learner_model import LearningEvent, SkillMastery
from app.models.practice import PracticeSession, PracticeSessionStatus
from app.models.progress import LessonAttempt, LessonAttemptStatus


def _utc_day_bounds(day: date) -> tuple[datetime, datetime]:
    """[start, end) for `day` in UTC. Same reasoning as
    gamification_repository._utc_day_bounds: `func.date(col) == day` would
    truncate using the Postgres session's TimeZone GUC rather than UTC,
    which is exactly the bug that surfaced live in Phase 9 - explicit UTC
    bounds sidesteps it entirely."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    return start, start + timedelta(days=1)


# --- AI call logging (written by app/ai/metering.py) ---


def record_ai_call(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    operation: AiCallOperation,
    provider: str,
    model: str | None,
    latency_ms: int,
    success: bool,
    error_type: str | None,
) -> AiCallLog:
    call_log = AiCallLog(
        user_id=user_id,
        operation=operation,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
    )
    db.add(call_log)
    db.flush()
    return call_log


def get_ai_call_stats(
    db: Session, *, since: datetime
) -> list[tuple[AiCallOperation, int, int, float]]:
    """Per operation since `since`: (operation, total_calls, failed_calls,
    avg_latency_ms)."""
    stmt = (
        select(
            AiCallLog.operation,
            func.count(),
            func.sum(case((AiCallLog.success.is_(False), 1), else_=0)),
            func.avg(AiCallLog.latency_ms),
        )
        .where(AiCallLog.created_at >= since)
        .group_by(AiCallLog.operation)
    )
    return [
        (op, int(total), int(failed or 0), float(avg_latency or 0.0))
        for op, total, failed, avg_latency in db.execute(stmt).all()
    ]


# --- Daily active users ---


def get_daily_active_user_counts(
    db: Session, *, since_day: date, until_day: date
) -> list[tuple[date, int]]:
    """One row per day in [since_day, until_day] (inclusive), counting
    distinct users with a LearningEvent that day. Queried day-by-day with
    explicit UTC bounds rather than a single date_trunc(...) grouped query -
    see _utc_day_bounds - to stay consistent with the one bucketing approach
    already proven correct in this codebase."""
    results = []
    day = since_day
    while day <= until_day:
        start, end = _utc_day_bounds(day)
        stmt = select(func.count(func.distinct(LearningEvent.user_id))).where(
            LearningEvent.created_at >= start, LearningEvent.created_at < end
        )
        results.append((day, int(db.execute(stmt).scalar_one())))
        day += timedelta(days=1)
    return results


# --- Lesson / practice completion ---


def get_lesson_completion_stats(db: Session, *, since: datetime) -> tuple[int, int]:
    """(started, completed) among LessonAttempts started since `since`."""
    stmt = select(
        func.count(),
        func.sum(case((LessonAttempt.status == LessonAttemptStatus.COMPLETED, 1), else_=0)),
    ).where(LessonAttempt.started_at >= since)
    started, completed = db.execute(stmt).one()
    return int(started), int(completed or 0)


def get_practice_completion_stats(db: Session, *, since: datetime) -> tuple[int, int]:
    """(started, completed) among PracticeSessions started since `since`."""
    stmt = select(
        func.count(),
        func.sum(case((PracticeSession.status == PracticeSessionStatus.COMPLETED, 1), else_=0)),
    ).where(PracticeSession.started_at >= since)
    started, completed = db.execute(stmt).one()
    return int(started), int(completed or 0)


# --- Retention ---


def get_day_n_retention(db: Session, *, reference_day: date, n: int) -> tuple[int, int]:
    """Of users with a LearningEvent on (reference_day - n), how many also
    had one on reference_day? Returns (cohort_size, retained_count). A
    simple, standard N-day-return definition - not first-ever-activity
    cohorting, which would need per-user "first seen" bookkeeping this
    schema doesn't have."""
    cohort_start, cohort_end = _utc_day_bounds(reference_day - timedelta(days=n))
    cohort_stmt = select(func.distinct(LearningEvent.user_id)).where(
        LearningEvent.created_at >= cohort_start, LearningEvent.created_at < cohort_end
    )
    cohort_ids = set(db.execute(cohort_stmt).scalars().all())
    if not cohort_ids:
        return 0, 0

    ref_start, ref_end = _utc_day_bounds(reference_day)
    retained_stmt = select(func.distinct(LearningEvent.user_id)).where(
        LearningEvent.user_id.in_(cohort_ids),
        LearningEvent.created_at >= ref_start,
        LearningEvent.created_at < ref_end,
    )
    retained_ids = set(db.execute(retained_stmt).scalars().all())
    return len(cohort_ids), len(retained_ids)


# --- Mistakes / weakest skills ---


def get_top_mistake_types(
    db: Session, *, since: datetime, limit: int
) -> list[tuple[DetectedErrorType, int]]:
    stmt = (
        select(DetectedError.error_type, func.count())
        .where(DetectedError.created_at >= since)
        .group_by(DetectedError.error_type)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [(error_type, int(count)) for error_type, count in db.execute(stmt).all()]


def get_weakest_skills(
    db: Session, *, limit: int
) -> list[tuple[uuid.UUID, str, float, int]]:
    """(skill_id, skill_name, avg_mastery, total_attempts) for skills that
    have at least one SkillMastery row, ordered by weakest mastery first.
    Skills nobody has attempted yet are excluded - there's no mastery signal
    to call "weak"."""
    stmt = (
        select(
            Skill.id,
            Skill.name,
            func.avg(SkillMastery.mastery),
            func.sum(SkillMastery.attempt_count),
        )
        .join(SkillMastery, SkillMastery.skill_id == Skill.id)
        .group_by(Skill.id, Skill.name)
        .having(func.sum(SkillMastery.attempt_count) > 0)
        .order_by(func.avg(SkillMastery.mastery).asc())
        .limit(limit)
    )
    return [
        (skill_id, name, float(avg_mastery), int(total_attempts))
        for skill_id, name, avg_mastery, total_attempts in db.execute(stmt).all()
    ]


# --- Improvement over time ---


def get_weekly_correctness_trend(
    db: Session, *, num_weeks: int, end_day: date
) -> list[tuple[date, int, int]]:
    """Last `num_weeks` Mon-Sun UTC weeks up to and including end_day's
    week, oldest first: (week_start, correct_count, total_count) from
    LearningEvent."""
    current_week_start = end_day - timedelta(days=end_day.weekday())
    results = []
    for i in range(num_weeks):
        week_start = current_week_start - timedelta(weeks=(num_weeks - 1 - i))
        start, _ = _utc_day_bounds(week_start)
        _, end = _utc_day_bounds(week_start + timedelta(days=6))
        stmt = select(
            func.count(),
            func.sum(case((LearningEvent.is_correct.is_(True), 1), else_=0)),
        ).where(LearningEvent.created_at >= start, LearningEvent.created_at < end)
        total, correct = db.execute(stmt).one()
        results.append((week_start, int(correct or 0), int(total or 0)))
    return results
