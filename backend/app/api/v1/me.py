from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import evaluation_repository, learner_model_repository, user_repository
from app.schemas.analytics import LearnerActivityOut
from app.schemas.auth import PreferencesOut, PreferencesUpdate, UserOut
from app.schemas.evaluation import DetectedErrorOut
from app.schemas.gamification import ProgressOut, QuestOut
from app.schemas.mastery import ReviewItemOut, SkillMasteryOut
from app.services import analytics_service, progress_service, quest_service

DEFAULT_ACTIVITY_WINDOW_DAYS = 30

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/progress", response_model=ProgressOut)
def get_my_progress(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProgressOut:
    return progress_service.get_progress(db, current_user)


@router.get("/mastery", response_model=list[SkillMasteryOut])
def get_my_mastery(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SkillMasteryOut]:
    rows = learner_model_repository.list_skill_mastery_for_user(db, current_user.id)
    return [SkillMasteryOut.from_model(row) for row in rows]


@router.get("/review", response_model=list[ReviewItemOut])
def get_my_review_queue(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ReviewItemOut]:
    rows = learner_model_repository.list_due_for_review(
        db, user_id=current_user.id, now=datetime.now(UTC)
    )
    return [ReviewItemOut.from_model(row) for row in rows]


@router.get("/activity", response_model=LearnerActivityOut)
def get_my_activity(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> LearnerActivityOut:
    """Real, learner-scoped analytics for the redesigned Progress page -
    lesson/practice completion and an 8-week accuracy trend, reusing the
    same UTC-safe aggregation techniques as the admin analytics dashboard
    (analytics_service.get_overview), scoped to this user."""
    activity = analytics_service.get_learner_activity(
        db, user_id=current_user.id, days=DEFAULT_ACTIVITY_WINDOW_DAYS
    )
    return LearnerActivityOut.from_activity(activity)


@router.get("/errors", response_model=list[DetectedErrorOut])
def get_my_detected_errors(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DetectedErrorOut]:
    rows = evaluation_repository.list_recent_errors(db, current_user.id)
    return [DetectedErrorOut.from_model(row) for row in rows]


@router.get("/quests", response_model=list[QuestOut])
def get_my_quests(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[QuestOut]:
    today = datetime.now(UTC).date()
    progress = quest_service.get_quest_progress(db, current_user.id, today)
    return [
        QuestOut(
            id=q.id,
            quest_type=q.quest_type.value,
            name=q.name,
            description=q.description,
            target=q.target,
            progress=q.progress,
            reward_gems=q.reward_gems,
            completed=q.completed,
        )
        for q in progress
    ]


@router.patch("/preferences", response_model=PreferencesOut)
def update_my_preferences(
    payload: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferencesOut:
    prefs = user_repository.update_preferences(
        db,
        current_user,
        native_language=payload.native_language,
        target_language=payload.target_language,
        daily_goal_xp=payload.daily_goal_xp,
    )
    db.commit()
    return PreferencesOut.model_validate(prefs)
