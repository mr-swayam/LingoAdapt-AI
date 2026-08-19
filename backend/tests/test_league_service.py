import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.gamification import LeagueTier, XPReason
from app.repositories import gamification_repository
from app.services import league_service
from tests.auth_fixtures import create_user

MONDAY = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)  # a Monday
NEXT_MONDAY = MONDAY + timedelta(days=7)


def test_current_week_start_is_the_monday_of_that_week() -> None:
    wednesday = datetime(2026, 8, 19, 23, 0, tzinfo=UTC)
    assert league_service.current_week_start(wednesday) == date(2026, 8, 17)


def test_new_user_starts_in_spark_tier(db_session: Session) -> None:
    user = create_user(db_session, email="a@example.com")
    league = league_service.get_or_create_league(db_session, user.id, MONDAY)
    assert league.tier == LeagueTier.SPARK
    assert league.week_start == date(2026, 8, 17)


def test_reading_within_the_same_week_does_not_roll_over(db_session: Session) -> None:
    user = create_user(db_session, email="a@example.com")
    league_service.get_or_create_league(db_session, user.id, MONDAY)

    later_same_week = MONDAY + timedelta(days=3)
    league = league_service.get_or_create_league(db_session, user.id, later_same_week)
    assert league.week_start == date(2026, 8, 17)


def _give_xp(db: Session, user_id: uuid.UUID, amount: int) -> None:
    gamification_repository.record_xp_transaction(
        db, user_id=user_id, amount=amount, reason=XPReason.LESSON_COMPLETED, lesson_attempt_id=None
    )
    db.commit()


def test_small_cohort_never_moves_tier(db_session: Session) -> None:
    """Below MIN_COHORT_FOR_MOVEMENT, rolling into a new week resets the
    week but never promotes/demotes - not enough tier-mates to rank fairly.
    """
    user = create_user(db_session, email="solo@example.com")
    league_service.get_or_create_league(db_session, user.id, MONDAY)
    _give_xp(db_session, user.id, 100)

    league = league_service.get_or_create_league(db_session, user.id, NEXT_MONDAY)
    assert league.tier == LeagueTier.SPARK
    assert league.week_start == date(2026, 8, 24)


def test_top_of_a_real_cohort_gets_promoted(db_session: Session) -> None:
    users = [create_user(db_session, email=f"user{i}@example.com") for i in range(5)]
    for user in users:
        league_service.get_or_create_league(db_session, user.id, MONDAY)

    # Give the first user the most XP - should end up at the top of the cohort.
    _give_xp(db_session, users[0].id, 500)
    for user in users[1:]:
        _give_xp(db_session, user.id, 10)

    league = league_service.get_or_create_league(db_session, users[0].id, NEXT_MONDAY)
    assert league.tier == LeagueTier.EMBER  # promoted from SPARK


def test_bottom_of_a_real_cohort_is_demoted_from_a_higher_tier(db_session: Session) -> None:
    users = [create_user(db_session, email=f"demote{i}@example.com") for i in range(5)]
    for user in users:
        league = gamification_repository.get_user_league(db_session, user.id)
        if league is None:
            gamification_repository.create_user_league(
                db_session, user_id=user.id, tier=LeagueTier.BLAZE, week_start=date(2026, 8, 17)
            )
    db_session.commit()

    # Everyone earns XP except the last user, who should be demoted.
    for user in users[:-1]:
        _give_xp(db_session, user.id, 50)

    league = league_service.get_or_create_league(db_session, users[-1].id, NEXT_MONDAY)
    assert league.tier == LeagueTier.EMBER  # demoted from BLAZE


def test_leaderboard_ranks_by_weekly_xp_descending(db_session: Session) -> None:
    a = create_user(db_session, email="alice@example.com")
    b = create_user(db_session, email="bob@example.com")
    league_service.get_or_create_league(db_session, a.id, MONDAY)
    league_service.get_or_create_league(db_session, b.id, MONDAY)
    _give_xp(db_session, a.id, 20)
    _give_xp(db_session, b.id, 80)

    league = league_service.get_or_create_league(db_session, a.id, MONDAY)
    entries = league_service.get_league_leaderboard(db_session, league, a.id)

    assert [e.email for e in entries] == ["bob@example.com", "alice@example.com"]
    assert entries[0].rank == 1
    assert entries[1].rank == 2
    assert entries[1].is_me is True
