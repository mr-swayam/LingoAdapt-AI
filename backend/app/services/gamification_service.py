"""Deterministic gamification: XP, streaks, achievements. No AI involved -
rules.md requires XP/streaks/rewards to be server-owned and deterministic.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.gamification import CurrencyReason, XPReason
from app.models.progress import LessonAttempt
from app.repositories import gamification_repository, social_repository
from app.services import currency_service
from app.services.streak import compute_streak_update

XP_PER_CORRECT_ANSWER = 10
ACHIEVEMENT_GEM_REWARD = 20


def compute_lesson_xp(correct_count: int) -> int:
    """Isolated so the reward formula can be tuned without touching callers."""
    return correct_count * XP_PER_CORRECT_ANSWER


@dataclass(frozen=True)
class AchievementContext:
    total_xp: int
    current_streak: int
    lessons_completed: int
    last_lesson_perfect: bool
    quests_completed_total: int
    friends_count: int
    league_promoted: bool


@dataclass(frozen=True)
class AchievementDef:
    code: str
    name: str
    description: str
    condition: Callable[[AchievementContext], bool]


ACHIEVEMENT_CATALOG: list[AchievementDef] = [
    AchievementDef(
        "FIRST_LESSON",
        "First Steps",
        "Complete your first lesson.",
        lambda ctx: ctx.lessons_completed >= 1,
    ),
    AchievementDef(
        "PERFECT_LESSON",
        "Perfectionist",
        "Complete a lesson with a perfect score.",
        lambda ctx: ctx.last_lesson_perfect,
    ),
    AchievementDef(
        "STREAK_3",
        "On a Roll",
        "Reach a 3-day streak.",
        lambda ctx: ctx.current_streak >= 3,
    ),
    AchievementDef(
        "XP_100",
        "Century Club",
        "Earn 100 total XP.",
        lambda ctx: ctx.total_xp >= 100,
    ),
    AchievementDef(
        "QUEST_MASTER",
        "Quest Master",
        "Complete 10 daily quests.",
        lambda ctx: ctx.quests_completed_total >= 10,
    ),
    AchievementDef(
        "FIRST_FRIEND",
        "Study Buddy",
        "Add your first friend.",
        lambda ctx: ctx.friends_count >= 1,
    ),
    AchievementDef(
        "RISING_STAR",
        "Rising Star",
        "Get promoted to a higher league.",
        lambda ctx: ctx.league_promoted,
    ),
]


def _build_achievement_context(
    db: Session,
    user_id: uuid.UUID,
    *,
    current_streak: int,
    last_lesson_perfect: bool = False,
    league_promoted: bool = False,
) -> AchievementContext:
    return AchievementContext(
        total_xp=gamification_repository.get_total_xp(db, user_id),
        current_streak=current_streak,
        lessons_completed=gamification_repository.count_distinct_completed_lessons(db, user_id),
        last_lesson_perfect=last_lesson_perfect,
        quests_completed_total=gamification_repository.count_completed_quests(db, user_id),
        friends_count=social_repository.count_accepted_friends(db, user_id),
        league_promoted=league_promoted,
    )


def _evaluate_achievements(
    db: Session, *, user_id: uuid.UUID, context: AchievementContext
) -> list[AchievementDef]:
    already_earned_ids = {
        ua.achievement_id for ua in gamification_repository.get_user_achievements(db, user_id)
    }
    catalog_by_code = {a.code: a for a in gamification_repository.list_achievements(db)}

    newly_earned: list[AchievementDef] = []
    for achievement_def in ACHIEVEMENT_CATALOG:
        row = catalog_by_code.get(achievement_def.code)
        if row is None or row.id in already_earned_ids:
            continue
        if achievement_def.condition(context):
            earned = gamification_repository.award_achievement(
                db, user_id=user_id, achievement_id=row.id
            )
            currency_service.award_currency(
                db,
                user_id=user_id,
                amount=ACHIEVEMENT_GEM_REWARD,
                reason=CurrencyReason.ACHIEVEMENT_UNLOCKED,
                source_id=str(earned.id),
            )
            newly_earned.append(achievement_def)

    return newly_earned


def evaluate_achievements_for_user(
    db: Session, user_id: uuid.UUID, *, league_promoted: bool = False
) -> list[AchievementDef]:
    """General-purpose entry point for gamification actions outside lesson
    completion (quest completion, adding a friend, a league promotion) -
    rebuilds the full achievement context fresh from current state and
    checks every not-yet-earned achievement against it."""
    streak = gamification_repository.get_streak(db, user_id)
    context = _build_achievement_context(
        db,
        user_id,
        current_streak=streak.current_streak if streak else 0,
        league_promoted=league_promoted,
    )
    return _evaluate_achievements(db, user_id=user_id, context=context)


@dataclass(frozen=True)
class LessonRewards:
    xp_earned: int
    already_awarded: bool
    current_streak: int
    new_achievements: list[AchievementDef]


def apply_lesson_completion_rewards(
    db: Session, *, user_id: uuid.UUID, attempt: LessonAttempt
) -> LessonRewards:
    """Idempotent: safe to call every time a completed attempt is touched,
    including on an idempotent re-submission of an already-completed lesson.
    """
    existing = gamification_repository.get_xp_transaction_for_attempt(db, attempt.id)
    if existing is not None:
        streak = gamification_repository.get_streak(db, user_id)
        return LessonRewards(
            xp_earned=existing.amount,
            already_awarded=True,
            current_streak=streak.current_streak if streak else 0,
            new_achievements=[],
        )

    xp_earned = compute_lesson_xp(attempt.correct_count)
    gamification_repository.record_xp_transaction(
        db,
        user_id=user_id,
        amount=xp_earned,
        reason=XPReason.LESSON_COMPLETED,
        lesson_attempt_id=attempt.id,
    )

    streak_row = gamification_repository.get_streak(db, user_id)
    today = datetime.now(UTC).date()
    update = compute_streak_update(
        current_streak=streak_row.current_streak if streak_row else 0,
        longest_streak=streak_row.longest_streak if streak_row else 0,
        last_active_date=streak_row.last_active_date if streak_row else None,
        today=today,
    )
    gamification_repository.save_streak(
        db,
        user_id=user_id,
        current_streak=update.current_streak,
        longest_streak=update.longest_streak,
        last_active_date=today,
    )

    context = _build_achievement_context(
        db,
        user_id,
        current_streak=update.current_streak,
        last_lesson_perfect=attempt.correct_count == attempt.total_count,
    )
    new_achievements = _evaluate_achievements(db, user_id=user_id, context=context)

    return LessonRewards(
        xp_earned=xp_earned,
        already_awarded=False,
        current_streak=update.current_streak,
        new_achievements=new_achievements,
    )
