from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.gamification import AchievementOut
from app.services import progress_service

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("", response_model=list[AchievementOut])
def list_achievements(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AchievementOut]:
    return progress_service.build_achievements(db, current_user.id)
