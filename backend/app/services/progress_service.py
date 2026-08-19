import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import course_repository, gamification_repository
from app.schemas.gamification import (
    AchievementOut,
    CourseProgressOut,
    ProgressOut,
    XPTransactionOut,
)
from app.services import currency_service, league_service
from app.services.gamification_service import ACHIEVEMENT_CATALOG

RECENT_XP_HISTORY_LIMIT = 20


def _build_course_progress(db: Session, user_id: uuid.UUID) -> list[CourseProgressOut]:
    courses = course_repository.list_published_courses(db)
    result: list[CourseProgressOut] = []
    for course in courses:
        lesson_ids = [lesson.id for unit in course.units for lesson in unit.lessons]
        completed_ids = gamification_repository.get_completed_lesson_ids(db, user_id, lesson_ids)
        total = len(lesson_ids)
        percent = (len(completed_ids) / total * 100) if total else 0.0
        result.append(
            CourseProgressOut(
                course_id=course.id,
                course_title=course.title,
                completed_lessons=len(completed_ids),
                total_lessons=total,
                percent_complete=round(percent, 1),
            )
        )
    return result


def build_achievements(db: Session, user_id: uuid.UUID) -> list[AchievementOut]:
    catalog = {a.code: a for a in gamification_repository.list_achievements(db)}
    earned_by_achievement_id = {
        ua.achievement_id: ua.earned_at
        for ua in gamification_repository.get_user_achievements(db, user_id)
    }

    result: list[AchievementOut] = []
    for achievement_def in ACHIEVEMENT_CATALOG:
        row = catalog.get(achievement_def.code)
        earned_at = earned_by_achievement_id.get(row.id) if row else None
        result.append(
            AchievementOut(
                code=achievement_def.code,
                name=achievement_def.name,
                description=achievement_def.description,
                earned=earned_at is not None,
                earned_at=earned_at,
            )
        )
    return result


def get_progress(db: Session, user: User) -> ProgressOut:
    streak = gamification_repository.get_streak(db, user.id)
    now = datetime.now(UTC)
    today = now.date()

    recent = gamification_repository.list_recent_xp_transactions(
        db, user.id, RECENT_XP_HISTORY_LIMIT
    )
    league = league_service.get_or_create_league(db, user.id, now)

    return ProgressOut(
        total_xp=gamification_repository.get_total_xp(db, user.id),
        xp_today=gamification_repository.get_xp_earned_on(db, user.id, today),
        daily_goal_xp=user.preferences.daily_goal_xp,
        current_streak=streak.current_streak if streak else 0,
        longest_streak=streak.longest_streak if streak else 0,
        course_progress=_build_course_progress(db, user.id),
        achievements=build_achievements(db, user.id),
        recent_xp_transactions=[
            XPTransactionOut(amount=t.amount, reason=t.reason.value, created_at=t.created_at)
            for t in recent
        ],
        gem_balance=currency_service.get_balance(db, user.id),
        league_tier=league.tier.value,
    )
