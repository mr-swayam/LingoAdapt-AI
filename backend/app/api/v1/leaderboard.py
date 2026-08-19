from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.gamification import LeaderboardEntryOut, LeagueLeaderboardOut
from app.services import friend_service, league_service

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


def _to_entry_out(entry: league_service.LeaderboardEntry) -> LeaderboardEntryOut:
    return LeaderboardEntryOut(
        email=entry.email, weekly_xp=entry.weekly_xp, rank=entry.rank, is_me=entry.is_me
    )


@router.get("", response_model=LeagueLeaderboardOut)
def get_league_leaderboard(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> LeagueLeaderboardOut:
    now = datetime.now(UTC)
    league = league_service.get_or_create_league(db, current_user.id, now)
    entries = league_service.get_league_leaderboard(db, league, current_user.id)
    return LeagueLeaderboardOut(
        tier=league.tier.value,
        week_start=league.week_start,
        entries=[_to_entry_out(e) for e in entries],
    )


@router.get("/friends", response_model=list[LeaderboardEntryOut])
def get_friends_leaderboard(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[LeaderboardEntryOut]:
    now = datetime.now(UTC)
    entries = friend_service.get_friends_leaderboard(db, current_user.id, now)
    return [_to_entry_out(e) for e in entries]
