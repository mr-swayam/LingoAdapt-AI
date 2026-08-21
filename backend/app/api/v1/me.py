import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.api.deps import coach_refresh_rate_limit_gate, get_current_user, get_metered_ai_provider
from app.core.db import get_db
from app.models.course import ExerciseType
from app.models.user import User
from app.repositories import evaluation_repository, learner_model_repository, user_repository
from app.schemas.analytics import LearnerActivityOut
from app.schemas.auth import PreferencesOut, PreferencesUpdate, UserOut
from app.schemas.coach import CoachResponseOut
from app.schemas.daily_plan import DailyPlanOut
from app.schemas.evaluation import DetectedErrorOut
from app.schemas.gamification import ProgressOut, QuestOut
from app.schemas.mastery import ReviewItemOut, SkillMasteryOut
from app.schemas.mistakes import MistakeListOut, MistakeSource, RepeatedMistakeGroupOut
from app.services import (
    analytics_service,
    coach_service,
    daily_plan_service,
    mistake_service,
    progress_service,
    quest_service,
)

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


@router.get("/mistakes", response_model=MistakeListOut)
def get_my_mistakes(
    limit: int = Query(mistake_service.DEFAULT_MISTAKE_PAGE_SIZE, ge=1),
    offset: int = Query(0, ge=0),
    skill_id: uuid.UUID | None = Query(None),
    source: MistakeSource | None = Query(None),
    exercise_type: ExerciseType | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MistakeListOut:
    """V3.3 Mistake Notebook. Unifies wrong lesson/practice exercise
    attempts and tutor-conversation corrections into one newest-first,
    correctly-paginated list - see mistake_service.list_mistakes."""
    return mistake_service.list_mistakes(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        skill_id=skill_id,
        source=source,
        exercise_type=exercise_type,
    )


@router.get("/mistakes/repeated", response_model=list[RepeatedMistakeGroupOut])
def get_my_repeated_mistakes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[RepeatedMistakeGroupOut]:
    """Type A (repeated difficulty) / Type B (repeated exact mistake)
    groups over the learner's recent mistakes - see mistake_service.
    group_repeated_mistakes."""
    recent = mistake_service.list_mistakes(
        db, user_id=current_user.id, limit=mistake_service.REPEATED_MISTAKES_SCAN_LIMIT, offset=0
    )
    return mistake_service.group_repeated_mistakes(recent.items)


@router.get("/daily-plan", response_model=DailyPlanOut)
def get_my_daily_plan(
    local_date: date | None = Query(
        None,
        description=(
            "Learner's current browser-local date (YYYY-MM-DD). "
            "Falls back to UTC-today when omitted."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyPlanOut:
    """V3.2 Personalized Daily Plan - generated fresh on every request from
    live data, never persisted. See daily_plan_service.get_daily_plan."""
    return daily_plan_service.get_daily_plan(db, user_id=current_user.id, local_date=local_date)


@router.get("/coach", response_model=CoachResponseOut)
async def get_my_coach_insight(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> CoachResponseOut:
    """V3.1 AI Learning Coach. Serves a cached insight when one exists and
    hasn't been invalidated by real activity since; otherwise generates and
    caches a new one (or returns the deterministic insufficient-data
    message, at zero AI cost, for a learner with no history yet)."""
    result = await coach_service.get_coach_insight(
        db, user_id=current_user.id, ai_provider=ai_provider
    )
    return CoachResponseOut.from_result(result)


@router.post("/coach/refresh", response_model=CoachResponseOut)
async def refresh_my_coach_insight(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
    _cooldown: None = Depends(coach_refresh_rate_limit_gate),
) -> CoachResponseOut:
    """Explicit "Refresh" action - always bypasses the cache, gated by its
    own tighter cooldown (on top of the shared AI budget) so rapid repeated
    presses can't eat into it (V3 architecture review item 15)."""
    result = await coach_service.get_coach_insight(
        db, user_id=current_user.id, ai_provider=ai_provider, force_refresh=True
    )
    return CoachResponseOut.from_result(result)


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
