"""Phase 11: read-only aggregation for the admin analytics dashboard.
Every number here is computed deterministically from already-persisted
events (LearningEvent, LessonAttempt, PracticeSession, DetectedError,
SkillMastery, AiCallLog) - never from an LLM, per rules.md §2.1.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.analytics import AiCallOperation
from app.models.evaluation import DetectedErrorType
from app.repositories import analytics_repository

RETENTION_REFERENCE_OFFSET_DAYS = 1  # "yesterday" - today's data is still partial
IMPROVEMENT_TREND_WEEKS = 8
TOP_MISTAKES_LIMIT = 5
WEAKEST_SKILLS_LIMIT = 5


@dataclass(frozen=True)
class DailyActiveUsersPoint:
    day: str
    count: int


@dataclass(frozen=True)
class CompletionStats:
    started: int
    completed: int


@dataclass(frozen=True)
class RetentionPoint:
    cohort_size: int
    retained: int


@dataclass(frozen=True)
class AiOperationStats:
    operation: AiCallOperation
    total_calls: int
    failed_calls: int
    avg_latency_ms: float


@dataclass(frozen=True)
class MistakeTypeCount:
    error_type: DetectedErrorType
    count: int


@dataclass(frozen=True)
class WeakestSkill:
    skill_id: uuid.UUID
    skill_name: str
    avg_mastery: float
    total_attempts: int


@dataclass(frozen=True)
class WeeklyCorrectnessPoint:
    week_start: str
    correct: int
    total: int


@dataclass(frozen=True)
class AnalyticsOverview:
    daily_active_users: list[DailyActiveUsersPoint]
    lesson_completion: CompletionStats
    practice_completion: CompletionStats
    day1_retention: RetentionPoint
    day7_retention: RetentionPoint
    ai_stats: list[AiOperationStats]
    top_mistakes: list[MistakeTypeCount]
    weakest_skills: list[WeakestSkill]
    improvement_trend: list[WeeklyCorrectnessPoint]


def get_overview(db: Session, *, days: int) -> AnalyticsOverview:
    now = datetime.now(UTC)
    today = now.date()
    since_day = today - timedelta(days=days - 1)
    since_dt = datetime.combine(since_day, datetime.min.time(), tzinfo=UTC)

    dau = analytics_repository.get_daily_active_user_counts(
        db, since_day=since_day, until_day=today
    )

    lesson_started, lesson_completed = analytics_repository.get_lesson_completion_stats(
        db, since=since_dt
    )
    practice_started, practice_completed = analytics_repository.get_practice_completion_stats(
        db, since=since_dt
    )

    reference_day = today - timedelta(days=RETENTION_REFERENCE_OFFSET_DAYS)
    day1_cohort, day1_retained = analytics_repository.get_day_n_retention(
        db, reference_day=reference_day, n=1
    )
    day7_cohort, day7_retained = analytics_repository.get_day_n_retention(
        db, reference_day=reference_day, n=7
    )

    ai_stats = analytics_repository.get_ai_call_stats(db, since=since_dt)

    top_mistakes = analytics_repository.get_top_mistake_types(
        db, since=since_dt, limit=TOP_MISTAKES_LIMIT
    )

    weakest_skills = analytics_repository.get_weakest_skills(db, limit=WEAKEST_SKILLS_LIMIT)

    weekly_trend = analytics_repository.get_weekly_correctness_trend(
        db, num_weeks=IMPROVEMENT_TREND_WEEKS, end_day=today
    )

    return AnalyticsOverview(
        daily_active_users=[
            DailyActiveUsersPoint(day=day.isoformat(), count=count) for day, count in dau
        ],
        lesson_completion=CompletionStats(started=lesson_started, completed=lesson_completed),
        practice_completion=CompletionStats(
            started=practice_started, completed=practice_completed
        ),
        day1_retention=RetentionPoint(cohort_size=day1_cohort, retained=day1_retained),
        day7_retention=RetentionPoint(cohort_size=day7_cohort, retained=day7_retained),
        ai_stats=[
            AiOperationStats(
                operation=op, total_calls=total, failed_calls=failed, avg_latency_ms=avg_latency
            )
            for op, total, failed, avg_latency in ai_stats
        ],
        top_mistakes=[
            MistakeTypeCount(error_type=error_type, count=count)
            for error_type, count in top_mistakes
        ],
        weakest_skills=[
            WeakestSkill(
                skill_id=skill_id,
                skill_name=name,
                avg_mastery=avg_mastery,
                total_attempts=total_attempts,
            )
            for skill_id, name, avg_mastery, total_attempts in weakest_skills
        ],
        improvement_trend=[
            WeeklyCorrectnessPoint(week_start=week_start.isoformat(), correct=correct, total=total)
            for week_start, correct, total in weekly_trend
        ],
    )
