"""Weekly competitive leagues (phases.md Phase 9). No background job runner
exists in this stack, so promotion/demotion is computed lazily: whenever a
user's league state is read, if their `week_start` has fallen behind the
current calendar week, their just-finished week is scored against whichever
tier-mates still share that same (now-stale) `week_start` - a "cohort" that
forms naturally from shared activity cadence rather than a fixed-size
matchmaking pool, and needs no scheduler to stay correct.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.gamification import LeagueTier, UserLeague
from app.models.user import User
from app.repositories import gamification_repository, user_repository
from app.services import gamification_service

TIERS: list[LeagueTier] = list(LeagueTier)

# A cohort smaller than this never promotes/demotes - not enough tier-mates
# for the ranking to mean anything, so members just roll into a fresh week
# at their current tier instead.
MIN_COHORT_FOR_MOVEMENT = 3
PROMOTION_ZONE_RATIO = 0.3
DEMOTION_ZONE_RATIO = 0.3


def current_week_start(now: datetime) -> date:
    today = now.astimezone(UTC).date()
    return today - timedelta(days=today.weekday())  # Monday


def _rank_cohort(db: Session, *, tier: LeagueTier, week_start: date) -> list[tuple[uuid.UUID, int]]:
    """Cohort members ranked by their finished week's XP, highest first."""
    member_ids = gamification_repository.list_cohort_user_ids(db, tier=tier, week_start=week_start)
    week_end = week_start + timedelta(days=7)
    xp_by_user = gamification_repository.get_weekly_xp_for_users(
        db, member_ids, since=datetime.combine(week_start, datetime.min.time(), tzinfo=UTC),
        until=datetime.combine(week_end, datetime.min.time(), tzinfo=UTC),
    )
    return sorted(xp_by_user.items(), key=lambda pair: (-pair[1], pair[0].hex))


def _next_tier(tier: LeagueTier, *, up: bool) -> LeagueTier:
    index = TIERS.index(tier)
    if up:
        return TIERS[min(index + 1, len(TIERS) - 1)]
    return TIERS[max(index - 1, 0)]


def _roll_over_if_due(db: Session, league: UserLeague, now: datetime) -> UserLeague:
    new_week_start = current_week_start(now)
    if league.week_start >= new_week_start:
        return league

    ranked = _rank_cohort(db, tier=league.tier, week_start=league.week_start)
    cohort_size = len(ranked)
    old_tier = league.tier
    new_tier = old_tier

    if cohort_size >= MIN_COHORT_FOR_MOVEMENT:
        rank_index = next((i for i, (uid, _) in enumerate(ranked) if uid == league.user_id), None)
        if rank_index is not None:
            promotion_cutoff = max(1, round(cohort_size * PROMOTION_ZONE_RATIO))
            demotion_cutoff = max(1, round(cohort_size * DEMOTION_ZONE_RATIO))
            if rank_index < promotion_cutoff:
                new_tier = _next_tier(old_tier, up=True)
            elif rank_index >= cohort_size - demotion_cutoff:
                new_tier = _next_tier(old_tier, up=False)

    updated = gamification_repository.update_user_league(
        db, league=league, tier=new_tier, week_start=new_week_start
    )
    if TIERS.index(new_tier) > TIERS.index(old_tier):
        gamification_service.evaluate_achievements_for_user(
            db, league.user_id, league_promoted=True
        )
    return updated


def get_or_create_league(db: Session, user_id: uuid.UUID, now: datetime) -> UserLeague:
    """Creates a league row (new user) or applies a lazy rollover (stale
    week_start) as a side effect of a read - deliberately committed here
    rather than left to the caller, since callers as innocuous as `GET
    /me/progress` need this to actually persist rather than being silently
    discarded when the request's DB session closes without a commit."""
    league = gamification_repository.get_user_league(db, user_id)
    if league is None:
        league = gamification_repository.create_user_league(
            db, user_id=user_id, tier=LeagueTier.SPARK, week_start=current_week_start(now)
        )
        db.commit()
        return league

    rolled_over = _roll_over_if_due(db, league, now)
    db.commit()
    return rolled_over


def was_ever_promoted(league: UserLeague) -> bool:
    return TIERS.index(league.tier) > 0


@dataclass(frozen=True)
class LeaderboardEntry:
    user_id: uuid.UUID
    email: str
    weekly_xp: int
    rank: int
    is_me: bool


def get_league_leaderboard(
    db: Session, league: UserLeague, user_id: uuid.UUID
) -> list[LeaderboardEntry]:
    """Ranks `league`'s tier/week_start cohort - call get_or_create_league()
    first (once) to get an up-to-date league; this function does no
    rollover of its own."""
    ranked = _rank_cohort(db, tier=league.tier, week_start=league.week_start)

    users_by_id: dict[uuid.UUID, User] = {}
    for uid, _ in ranked:
        found = user_repository.get_by_id(db, uid)
        if found is not None:
            users_by_id[uid] = found

    return [
        LeaderboardEntry(
            user_id=uid,
            email=users_by_id[uid].email if uid in users_by_id else "unknown",
            weekly_xp=xp,
            rank=i + 1,
            is_me=uid == user_id,
        )
        for i, (uid, xp) in enumerate(ranked)
    ]
