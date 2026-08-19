import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models.gamification import QuestType, XPReason
from app.repositories import gamification_repository
from app.services import currency_service, gamification_service, quest_service
from tests.auth_fixtures import create_user
from tests.gamification_fixtures import seed_achievement_catalog

# Computed at import time, not hardcoded: XP transactions get a real
# server-side now() timestamp, so "today" here must track the same UTC
# clock or the two drift apart right at the day boundary - exactly the
# class of bug app.repositories.gamification_repository._utc_day_bounds
# was written to avoid on the app side (see its docstring).
TODAY = datetime.now(UTC).date()


def _give_xp(db: Session, user_id: uuid.UUID, amount: int) -> None:
    gamification_repository.record_xp_transaction(
        db, user_id=user_id, amount=amount, reason=XPReason.LESSON_COMPLETED, lesson_attempt_id=None
    )
    db.commit()


def test_ensure_daily_quests_creates_all_templates_once(db_session: Session) -> None:
    user = create_user(db_session, email="a@example.com")

    first = quest_service.ensure_daily_quests(db_session, user.id, TODAY)
    assert len(first) == len(quest_service.QUEST_TEMPLATES)

    second = quest_service.ensure_daily_quests(db_session, user.id, TODAY)
    assert {q.id for q in second} == {q.id for q in first}  # idempotent, not duplicated


def test_quest_progress_reflects_real_xp_earned_today(db_session: Session) -> None:
    user = create_user(db_session, email="a@example.com")
    _give_xp(db_session, user.id, 15)

    progress = quest_service.get_quest_progress(db_session, user.id, TODAY)
    xp_quest = next(q for q in progress if q.quest_type == QuestType.EARN_XP)

    assert xp_quest.progress == 15
    assert xp_quest.target == 30
    assert xp_quest.completed is False


def test_completing_a_quest_awards_currency_and_marks_complete(db_session: Session) -> None:
    user = create_user(db_session, email="a@example.com")
    _give_xp(db_session, user.id, 30)

    progress = quest_service.get_quest_progress(db_session, user.id, TODAY)
    xp_quest = next(q for q in progress if q.quest_type == QuestType.EARN_XP)

    assert xp_quest.completed is True
    assert xp_quest.newly_completed is True
    assert currency_service.get_balance(db_session, user.id) == xp_quest.reward_gems


def test_re_reading_an_already_completed_quest_does_not_double_award(db_session: Session) -> None:
    user = create_user(db_session, email="a@example.com")
    _give_xp(db_session, user.id, 30)

    first = quest_service.get_quest_progress(db_session, user.id, TODAY)
    balance_after_first = currency_service.get_balance(db_session, user.id)

    second = quest_service.get_quest_progress(db_session, user.id, TODAY)
    xp_quest_second = next(q for q in second if q.quest_type == QuestType.EARN_XP)

    assert xp_quest_second.newly_completed is False
    assert xp_quest_second.completed is True
    assert currency_service.get_balance(db_session, user.id) == balance_after_first
    assert len(first) == len(second)


def test_progress_never_exceeds_target_even_if_overshot(db_session: Session) -> None:
    user = create_user(db_session, email="a@example.com")
    _give_xp(db_session, user.id, 999)

    progress = quest_service.get_quest_progress(db_session, user.id, TODAY)
    xp_quest = next(q for q in progress if q.quest_type == QuestType.EARN_XP)
    assert xp_quest.progress == xp_quest.target


def test_completing_ten_quests_unlocks_quest_master_achievement(db_session: Session) -> None:
    """Completion is set up directly via the repository (bypassing the real
    XP/lesson/practice signals get_quest_progress would otherwise require)
    since what's under test here is the achievement threshold, not quest
    completion detection itself - that's covered by the tests above."""
    seed_achievement_catalog(db_session)
    user = create_user(db_session, email="a@example.com")

    for day_offset in range(4):  # 3 quest templates/day * 4 days = 12 completions
        day = date(2026, 8, 17 + day_offset)
        for template in quest_service.QUEST_TEMPLATES:
            quest = gamification_repository.create_daily_quest(
                db_session,
                user_id=user.id,
                quest_date=day,
                quest_type=template.quest_type,
                target=template.target,
                reward_gems=template.reward_gems,
            )
            gamification_repository.mark_quest_completed(
                db_session, quest=quest, completed_at=datetime.now(UTC)
            )
    db_session.commit()

    assert gamification_repository.count_completed_quests(db_session, user.id) >= 10

    new_achievements = gamification_service.evaluate_achievements_for_user(db_session, user.id)
    codes = {a.code for a in new_achievements}
    assert "QUEST_MASTER" in codes
    assert currency_service.get_balance(db_session, user.id) > 0
