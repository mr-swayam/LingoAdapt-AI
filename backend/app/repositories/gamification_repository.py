import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gamification import (
    Achievement,
    CurrencyReason,
    CurrencyTransaction,
    DailyQuest,
    LeagueTier,
    QuestType,
    Streak,
    UserAchievement,
    UserLeague,
    XPReason,
    XPTransaction,
)
from app.models.practice import PracticeSession, PracticeSessionStatus
from app.models.progress import LessonAttempt, LessonAttemptStatus


def _utc_day_bounds(day: date) -> tuple[datetime, datetime]:
    """[start, end) for `day` in UTC. Deliberately NOT `func.date(col) ==
    day` - that truncates using the Postgres session's TimeZone GUC (this
    deployment's is Asia/Calcutta, UTC+5:30), which disagrees with `day`
    whenever `day` came from Python's `datetime.now(UTC).date()` and the
    two zones are on different calendar dates - a real bug caught live
    (not just reasoned about) when this repo's dev DB crossed that exact
    boundary mid-test-run."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    return start, start + timedelta(days=1)


def get_xp_transaction_for_attempt(
    db: Session, lesson_attempt_id: uuid.UUID
) -> XPTransaction | None:
    stmt = select(XPTransaction).where(
        XPTransaction.lesson_attempt_id == lesson_attempt_id,
        XPTransaction.reason == XPReason.LESSON_COMPLETED,
    )
    return db.execute(stmt).scalar_one_or_none()


def record_xp_transaction(
    db: Session,
    *,
    user_id: uuid.UUID,
    amount: int,
    reason: XPReason,
    lesson_attempt_id: uuid.UUID | None,
) -> XPTransaction:
    transaction = XPTransaction(
        user_id=user_id, amount=amount, reason=reason, lesson_attempt_id=lesson_attempt_id
    )
    db.add(transaction)
    db.flush()
    return transaction


def get_total_xp(db: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
        XPTransaction.user_id == user_id
    )
    return int(db.execute(stmt).scalar_one())


def get_xp_earned_on(db: Session, user_id: uuid.UUID, day: date) -> int:
    start, end = _utc_day_bounds(day)
    stmt = select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
        XPTransaction.user_id == user_id,
        XPTransaction.created_at >= start,
        XPTransaction.created_at < end,
    )
    return int(db.execute(stmt).scalar_one())


def list_recent_xp_transactions(
    db: Session, user_id: uuid.UUID, limit: int
) -> list[XPTransaction]:
    stmt = (
        select(XPTransaction)
        .where(XPTransaction.user_id == user_id)
        .order_by(XPTransaction.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_streak(db: Session, user_id: uuid.UUID) -> Streak | None:
    return db.get(Streak, user_id)


def save_streak(
    db: Session,
    *,
    user_id: uuid.UUID,
    current_streak: int,
    longest_streak: int,
    last_active_date: date,
) -> Streak:
    streak = get_streak(db, user_id)
    if streak is None:
        streak = Streak(user_id=user_id)
        db.add(streak)
    streak.current_streak = current_streak
    streak.longest_streak = longest_streak
    streak.last_active_date = last_active_date
    db.flush()
    return streak


def list_achievements(db: Session) -> list[Achievement]:
    return list(db.execute(select(Achievement).order_by(Achievement.code)).scalars().all())


def get_achievement_by_code(db: Session, code: str) -> Achievement | None:
    return db.execute(select(Achievement).where(Achievement.code == code)).scalar_one_or_none()


def get_user_achievements(db: Session, user_id: uuid.UUID) -> list[UserAchievement]:
    stmt = select(UserAchievement).where(UserAchievement.user_id == user_id)
    return list(db.execute(stmt).scalars().all())


def award_achievement(
    db: Session, *, user_id: uuid.UUID, achievement_id: uuid.UUID
) -> UserAchievement:
    earned = UserAchievement(user_id=user_id, achievement_id=achievement_id)
    db.add(earned)
    db.flush()
    return earned


def count_distinct_completed_lessons(db: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.count(func.distinct(LessonAttempt.lesson_id))).where(
        LessonAttempt.user_id == user_id,
        LessonAttempt.status == LessonAttemptStatus.COMPLETED,
    )
    return int(db.execute(stmt).scalar_one())


def get_completed_lesson_ids(
    db: Session, user_id: uuid.UUID, lesson_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    if not lesson_ids:
        return set()
    stmt = select(func.distinct(LessonAttempt.lesson_id)).where(
        LessonAttempt.user_id == user_id,
        LessonAttempt.status == LessonAttemptStatus.COMPLETED,
        LessonAttempt.lesson_id.in_(lesson_ids),
    )
    return set(db.execute(stmt).scalars().all())


# --- Leagues ---


def get_user_league(db: Session, user_id: uuid.UUID) -> UserLeague | None:
    return db.get(UserLeague, user_id)


def create_user_league(
    db: Session, *, user_id: uuid.UUID, tier: LeagueTier, week_start: date
) -> UserLeague:
    league = UserLeague(user_id=user_id, tier=tier, week_start=week_start)
    db.add(league)
    db.flush()
    return league


def update_user_league(
    db: Session, *, league: UserLeague, tier: LeagueTier, week_start: date
) -> UserLeague:
    league.tier = tier
    league.week_start = week_start
    db.flush()
    return league


def list_cohort_user_ids(
    db: Session, *, tier: LeagueTier, week_start: date
) -> list[uuid.UUID]:
    stmt = select(UserLeague.user_id).where(
        UserLeague.tier == tier, UserLeague.week_start == week_start
    )
    return list(db.execute(stmt).scalars().all())


def get_weekly_xp_for_users(
    db: Session, user_ids: list[uuid.UUID], *, since: datetime, until: datetime
) -> dict[uuid.UUID, int]:
    if not user_ids:
        return {}
    stmt = (
        select(XPTransaction.user_id, func.coalesce(func.sum(XPTransaction.amount), 0))
        .where(
            XPTransaction.user_id.in_(user_ids),
            XPTransaction.created_at >= since,
            XPTransaction.created_at < until,
        )
        .group_by(XPTransaction.user_id)
    )
    totals = {user_id: int(total) for user_id, total in db.execute(stmt).all()}
    return {user_id: totals.get(user_id, 0) for user_id in user_ids}


# --- Daily quests ---


def get_daily_quests(db: Session, *, user_id: uuid.UUID, quest_date: date) -> list[DailyQuest]:
    stmt = select(DailyQuest).where(
        DailyQuest.user_id == user_id, DailyQuest.quest_date == quest_date
    )
    return list(db.execute(stmt).scalars().all())


def create_daily_quest(
    db: Session,
    *,
    user_id: uuid.UUID,
    quest_date: date,
    quest_type: QuestType,
    target: int,
    reward_gems: int,
) -> DailyQuest:
    quest = DailyQuest(
        user_id=user_id,
        quest_date=quest_date,
        quest_type=quest_type,
        target=target,
        reward_gems=reward_gems,
    )
    db.add(quest)
    db.flush()
    return quest


def mark_quest_completed(db: Session, *, quest: DailyQuest, completed_at: datetime) -> DailyQuest:
    quest.completed_at = completed_at
    db.flush()
    return quest


def count_completed_quests(db: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(
        DailyQuest.user_id == user_id, DailyQuest.completed_at.is_not(None)
    )
    return int(db.execute(stmt).scalar_one())


def count_completed_lessons_on(db: Session, user_id: uuid.UUID, day: date) -> int:
    start, end = _utc_day_bounds(day)
    stmt = select(func.count(func.distinct(LessonAttempt.lesson_id))).where(
        LessonAttempt.user_id == user_id,
        LessonAttempt.status == LessonAttemptStatus.COMPLETED,
        LessonAttempt.completed_at >= start,
        LessonAttempt.completed_at < end,
    )
    return int(db.execute(stmt).scalar_one())


def count_completed_practice_sessions_on(db: Session, user_id: uuid.UUID, day: date) -> int:
    start, end = _utc_day_bounds(day)
    stmt = select(func.count()).where(
        PracticeSession.user_id == user_id,
        PracticeSession.status == PracticeSessionStatus.COMPLETED,
        PracticeSession.completed_at >= start,
        PracticeSession.completed_at < end,
    )
    return int(db.execute(stmt).scalar_one())


# --- Virtual currency ---


def get_currency_balance(db: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(CurrencyTransaction.amount), 0)).where(
        CurrencyTransaction.user_id == user_id
    )
    return int(db.execute(stmt).scalar_one())


def get_currency_transaction(
    db: Session, *, source_id: str, reason: CurrencyReason
) -> CurrencyTransaction | None:
    stmt = select(CurrencyTransaction).where(
        CurrencyTransaction.source_id == source_id, CurrencyTransaction.reason == reason
    )
    return db.execute(stmt).scalar_one_or_none()


def record_currency_transaction(
    db: Session, *, user_id: uuid.UUID, amount: int, reason: CurrencyReason, source_id: str
) -> CurrencyTransaction:
    transaction = CurrencyTransaction(
        user_id=user_id, amount=amount, reason=reason, source_id=source_id
    )
    db.add(transaction)
    db.flush()
    return transaction


def list_recent_currency_transactions(
    db: Session, user_id: uuid.UUID, limit: int
) -> list[CurrencyTransaction]:
    stmt = (
        select(CurrencyTransaction)
        .where(CurrencyTransaction.user_id == user_id)
        .order_by(CurrencyTransaction.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
