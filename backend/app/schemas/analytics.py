import uuid

from pydantic import BaseModel

from app.models.analytics import AiCallOperation
from app.models.evaluation import DetectedErrorType
from app.services.analytics_service import AnalyticsOverview, LearnerActivity


class DailyActiveUsersPointOut(BaseModel):
    day: str
    count: int


class CompletionStatsOut(BaseModel):
    started: int
    completed: int
    completion_rate: float


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


class RetentionPointOut(BaseModel):
    cohort_size: int
    retained: int
    retention_rate: float


class AiOperationStatsOut(BaseModel):
    operation: AiCallOperation
    total_calls: int
    failed_calls: int
    error_rate: float
    avg_latency_ms: float


class MistakeTypeCountOut(BaseModel):
    error_type: DetectedErrorType
    count: int


class WeakestSkillOut(BaseModel):
    skill_id: uuid.UUID
    skill_name: str
    avg_mastery: float
    total_attempts: int


class WeeklyCorrectnessPointOut(BaseModel):
    week_start: str
    correct: int
    total: int
    accuracy: float


class LearnerActivityOut(BaseModel):
    """Real, learner-scoped activity for the redesigned /progress page -
    every field traces to a real query, no placeholder metrics."""

    lesson_completion: CompletionStatsOut
    practice_completion: CompletionStatsOut
    accuracy_trend: list[WeeklyCorrectnessPointOut]

    @classmethod
    def from_activity(cls, activity: LearnerActivity) -> "LearnerActivityOut":
        return cls(
            lesson_completion=CompletionStatsOut(
                started=activity.lesson_completion.started,
                completed=activity.lesson_completion.completed,
                completion_rate=_rate(
                    activity.lesson_completion.completed, activity.lesson_completion.started
                ),
            ),
            practice_completion=CompletionStatsOut(
                started=activity.practice_completion.started,
                completed=activity.practice_completion.completed,
                completion_rate=_rate(
                    activity.practice_completion.completed, activity.practice_completion.started
                ),
            ),
            accuracy_trend=[
                WeeklyCorrectnessPointOut(
                    week_start=p.week_start,
                    correct=p.correct,
                    total=p.total,
                    accuracy=_rate(p.correct, p.total),
                )
                for p in activity.accuracy_trend
            ],
        )


class AnalyticsOverviewOut(BaseModel):
    daily_active_users: list[DailyActiveUsersPointOut]
    lesson_completion: CompletionStatsOut
    practice_completion: CompletionStatsOut
    day1_retention: RetentionPointOut
    day7_retention: RetentionPointOut
    ai_stats: list[AiOperationStatsOut]
    top_mistakes: list[MistakeTypeCountOut]
    weakest_skills: list[WeakestSkillOut]
    improvement_trend: list[WeeklyCorrectnessPointOut]

    @classmethod
    def from_overview(cls, overview: AnalyticsOverview) -> "AnalyticsOverviewOut":
        return cls(
            daily_active_users=[
                DailyActiveUsersPointOut(day=p.day, count=p.count)
                for p in overview.daily_active_users
            ],
            lesson_completion=CompletionStatsOut(
                started=overview.lesson_completion.started,
                completed=overview.lesson_completion.completed,
                completion_rate=_rate(
                    overview.lesson_completion.completed, overview.lesson_completion.started
                ),
            ),
            practice_completion=CompletionStatsOut(
                started=overview.practice_completion.started,
                completed=overview.practice_completion.completed,
                completion_rate=_rate(
                    overview.practice_completion.completed, overview.practice_completion.started
                ),
            ),
            day1_retention=RetentionPointOut(
                cohort_size=overview.day1_retention.cohort_size,
                retained=overview.day1_retention.retained,
                retention_rate=_rate(
                    overview.day1_retention.retained, overview.day1_retention.cohort_size
                ),
            ),
            day7_retention=RetentionPointOut(
                cohort_size=overview.day7_retention.cohort_size,
                retained=overview.day7_retention.retained,
                retention_rate=_rate(
                    overview.day7_retention.retained, overview.day7_retention.cohort_size
                ),
            ),
            ai_stats=[
                AiOperationStatsOut(
                    operation=s.operation,
                    total_calls=s.total_calls,
                    failed_calls=s.failed_calls,
                    error_rate=_rate(s.failed_calls, s.total_calls),
                    avg_latency_ms=round(s.avg_latency_ms, 1),
                )
                for s in overview.ai_stats
            ],
            top_mistakes=[
                MistakeTypeCountOut(error_type=m.error_type, count=m.count)
                for m in overview.top_mistakes
            ],
            weakest_skills=[
                WeakestSkillOut(
                    skill_id=s.skill_id,
                    skill_name=s.skill_name,
                    avg_mastery=round(s.avg_mastery, 2),
                    total_attempts=s.total_attempts,
                )
                for s in overview.weakest_skills
            ],
            improvement_trend=[
                WeeklyCorrectnessPointOut(
                    week_start=p.week_start,
                    correct=p.correct,
                    total=p.total,
                    accuracy=_rate(p.correct, p.total),
                )
                for p in overview.improvement_trend
            ],
        )
