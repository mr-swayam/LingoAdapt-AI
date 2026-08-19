"""Daily quests (phases.md Phase 9). Every quest ties to a real learning
action already tracked elsewhere in the app (XP earned, a lesson finished,
a practice session completed) - rules.md §8.2/§8.3: reward meaningful
activity, not button-mashing. Progress is computed live from that existing
data on every read rather than mirrored into a separately-mutated counter,
the same style xp_today/streaks already use.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models.gamification import CurrencyReason, DailyQuest, QuestType
from app.repositories import gamification_repository
from app.services import currency_service, gamification_service


@dataclass(frozen=True)
class QuestTemplate:
    quest_type: QuestType
    target: int
    reward_gems: int
    name: str
    description: str


QUEST_TEMPLATES: list[QuestTemplate] = [
    QuestTemplate(
        QuestType.EARN_XP,
        target=30,
        reward_gems=10,
        name="Warm Up",
        description="Earn 30 XP today.",
    ),
    QuestTemplate(
        QuestType.COMPLETE_LESSON,
        target=1,
        reward_gems=15,
        name="Lesson Streak",
        description="Complete 1 lesson today.",
    ),
    QuestTemplate(
        QuestType.PRACTICE_SESSION,
        target=1,
        reward_gems=15,
        name="Sharpen Up",
        description="Finish a practice session today.",
    ),
]
_TEMPLATES_BY_TYPE = {t.quest_type: t for t in QUEST_TEMPLATES}


def ensure_daily_quests(db: Session, user_id: uuid.UUID, today: date) -> list[DailyQuest]:
    """Idempotent - a no-op after the first call each day."""
    existing = gamification_repository.get_daily_quests(db, user_id=user_id, quest_date=today)
    if existing:
        return existing

    return [
        gamification_repository.create_daily_quest(
            db,
            user_id=user_id,
            quest_date=today,
            quest_type=template.quest_type,
            target=template.target,
            reward_gems=template.reward_gems,
        )
        for template in QUEST_TEMPLATES
    ]


def _progress_for(db: Session, *, user_id: uuid.UUID, quest_type: QuestType, today: date) -> int:
    match quest_type:
        case QuestType.EARN_XP:
            return gamification_repository.get_xp_earned_on(db, user_id, today)
        case QuestType.COMPLETE_LESSON:
            return gamification_repository.count_completed_lessons_on(db, user_id, today)
        case QuestType.PRACTICE_SESSION:
            return gamification_repository.count_completed_practice_sessions_on(
                db, user_id, today
            )


@dataclass(frozen=True)
class QuestProgress:
    id: uuid.UUID
    quest_type: QuestType
    name: str
    description: str
    target: int
    progress: int
    reward_gems: int
    completed: bool
    newly_completed: bool


def get_quest_progress(db: Session, user_id: uuid.UUID, today: date) -> list[QuestProgress]:
    """Also awards currency the first time a quest is observed complete -
    called on every /me/quests read, so completion is detected as soon as
    the learner does the qualifying action and next looks at their quests.
    Commits internally (mirrors league_service.get_or_create_league) so
    quest creation/completion persists even though this is invoked from a
    GET endpoint, rather than being silently rolled back when the request's
    DB session closes without a commit.
    """
    quests = ensure_daily_quests(db, user_id, today)
    now = datetime.now(UTC)
    results: list[QuestProgress] = []

    for quest in quests:
        template = _TEMPLATES_BY_TYPE[quest.quest_type]
        progress = _progress_for(
            db, user_id=user_id, quest_type=quest.quest_type, today=today
        )
        newly_completed = False

        if quest.completed_at is None and progress >= quest.target:
            gamification_repository.mark_quest_completed(db, quest=quest, completed_at=now)
            currency_service.award_currency(
                db,
                user_id=user_id,
                amount=quest.reward_gems,
                reason=CurrencyReason.QUEST_COMPLETED,
                source_id=str(quest.id),
            )
            gamification_service.evaluate_achievements_for_user(db, user_id)
            newly_completed = True

        results.append(
            QuestProgress(
                id=quest.id,
                quest_type=quest.quest_type,
                name=template.name,
                description=template.description,
                target=quest.target,
                progress=min(progress, quest.target),
                reward_gems=quest.reward_gems,
                completed=quest.completed_at is not None or newly_completed,
                newly_completed=newly_completed,
            )
        )

    db.commit()
    return results
