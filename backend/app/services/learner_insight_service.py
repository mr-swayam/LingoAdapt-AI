"""Shared learner-insight aggregation layer (V3). The one place weak-skill/
accuracy/mistake-summary logic lives - the AI Coach, Daily Plan, and Mistake
Notebook all build on this rather than each recomputing their own version
(V3_REVISED_IMPLEMENTATION_PLAN.md §4). No new learner model, no duplicated
mastery/recommendation calculation: every function here either directly
reuses an existing repository/service call or is a small, explicit
aggregation over its output.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories import learner_model_repository
from app.services import analytics_service, mistake_service
from app.services.analytics_service import LearnerActivity

# Improving-skill thresholds (V3 architecture review item 16) - fixed now,
# not "decided during implementation": recent window = last 7 days,
# previous window = the 7 days before that; a skill is only evaluated if
# BOTH windows have at least 3 attempts (below that a swing is noise, not a
# trend); it counts as improving only with a recent-vs-previous accuracy
# delta >= 15 percentage points.
IMPROVING_SKILL_RECENT_WINDOW_DAYS = 7
IMPROVING_SKILL_MIN_ATTEMPTS_PER_WINDOW = 3
IMPROVING_SKILL_MIN_ACCURACY_DELTA = 15.0

DEFAULT_WEAK_SKILLS_LIMIT = 5
DEFAULT_IMPROVING_SKILLS_LIMIT = 5
ACTIVITY_SUMMARY_WINDOW_DAYS = 30


@dataclass(frozen=True)
class WeakSkill:
    skill_id: uuid.UUID
    skill_name: str
    mastery: float
    confidence: float
    attempt_count: int


@dataclass(frozen=True)
class ImprovingSkill:
    skill_id: uuid.UUID
    skill_name: str
    recent_accuracy: float
    previous_accuracy: float
    delta: float


@dataclass(frozen=True)
class ReviewPriority:
    skill_id: uuid.UUID
    skill_name: str
    next_review_at: datetime


def get_weak_skills(
    db: Session, *, user_id: uuid.UUID, limit: int = DEFAULT_WEAK_SKILLS_LIMIT
) -> list[WeakSkill]:
    """Pure reuse of SkillMastery, sorted ascending by mastery - the same
    snapshot the Practice page's recommendation engine and the Progress
    page's "weak skills" card already read, just packaged for V3's new
    consumers instead of recomputed."""
    rows = learner_model_repository.list_skill_mastery_for_user(db, user_id)
    attempted = sorted((r for r in rows if r.attempt_count > 0), key=lambda r: r.mastery)
    return [
        WeakSkill(
            skill_id=r.skill_id,
            skill_name=r.skill.name,
            mastery=r.mastery,
            confidence=r.confidence,
            attempt_count=r.attempt_count,
        )
        for r in attempted[:limit]
    ]


def get_improving_skills(
    db: Session, *, user_id: uuid.UUID, limit: int = DEFAULT_IMPROVING_SKILLS_LIMIT
) -> list[ImprovingSkill]:
    """Compares each attempted skill's last-7-days accuracy against the
    7 days before that, from the append-only LearningEvent log - see the
    fixed thresholds above. Not derived from SkillMastery.mastery (a
    snapshot with no history - see analytics_repository.
    get_weekly_correctness_trend_for_user's docstring), so this is real
    accuracy-over-time, not an inferred trend."""
    now = datetime.now(UTC)
    recent_start = now - timedelta(days=IMPROVING_SKILL_RECENT_WINDOW_DAYS)
    previous_start = now - timedelta(days=IMPROVING_SKILL_RECENT_WINDOW_DAYS * 2)

    rows = learner_model_repository.list_skill_mastery_for_user(db, user_id)
    improving: list[ImprovingSkill] = []
    for row in rows:
        recent_correct, recent_total = learner_model_repository.get_skill_accuracy_in_window(
            db, user_id=user_id, skill_id=row.skill_id, start=recent_start, end=now
        )
        previous_correct, previous_total = learner_model_repository.get_skill_accuracy_in_window(
            db, user_id=user_id, skill_id=row.skill_id, start=previous_start, end=recent_start
        )
        if (
            recent_total < IMPROVING_SKILL_MIN_ATTEMPTS_PER_WINDOW
            or previous_total < IMPROVING_SKILL_MIN_ATTEMPTS_PER_WINDOW
        ):
            continue

        recent_accuracy = (recent_correct / recent_total) * 100.0
        previous_accuracy = (previous_correct / previous_total) * 100.0
        delta = recent_accuracy - previous_accuracy
        if delta >= IMPROVING_SKILL_MIN_ACCURACY_DELTA:
            improving.append(
                ImprovingSkill(
                    skill_id=row.skill_id,
                    skill_name=row.skill.name,
                    recent_accuracy=recent_accuracy,
                    previous_accuracy=previous_accuracy,
                    delta=delta,
                )
            )

    improving.sort(key=lambda s: s.delta, reverse=True)
    return improving[:limit]


def get_review_priorities(db: Session, *, user_id: uuid.UUID) -> list[ReviewPriority]:
    """Pure reuse of list_due_for_review - the exact same query the Daily
    Plan's REVIEW tasks and the Progress page's "Due for review" card use."""
    now = datetime.now(UTC)
    rows = learner_model_repository.list_due_for_review(db, user_id=user_id, now=now)
    return [
        ReviewPriority(
            skill_id=r.skill_id, skill_name=r.skill.name, next_review_at=r.next_review_at
        )
        for r in rows
        if r.next_review_at is not None
    ]


def get_recent_activity_summary(db: Session, *, user_id: uuid.UUID) -> LearnerActivity:
    """Pure reuse of analytics_service.get_learner_activity - already real,
    already scoped to one learner, already tested (V2 redesign)."""
    return analytics_service.get_learner_activity(
        db, user_id=user_id, days=ACTIVITY_SUMMARY_WINDOW_DAYS
    )


def get_repeated_mistakes_summary(
    db: Session, *, user_id: uuid.UUID
) -> mistake_service.RepeatedMistakesSummary:
    """Delegates to mistake_service - the Type A/B grouping logic lives in
    exactly one place (mistake_service.group_repeated_mistakes), not
    reimplemented here for a second, lighter-weight consumer."""
    return mistake_service.get_repeated_mistakes_summary(db, user_id=user_id)


def has_any_learning_history(db: Session, *, user_id: uuid.UUID) -> bool:
    """The AI Coach's insufficient-data short-circuit test (V3.1): true once
    the learner has attempted at least one skill."""
    rows = learner_model_repository.list_skill_mastery_for_user(db, user_id)
    return any(r.attempt_count > 0 for r in rows)
