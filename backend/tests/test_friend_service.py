from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.gamification import XPReason
from app.models.social import FriendshipStatus
from app.repositories import gamification_repository
from app.services import friend_service
from tests.auth_fixtures import create_user
from tests.gamification_fixtures import seed_achievement_catalog


def test_send_request_creates_pending_friendship(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    b = create_user(db_session, email="b@example.com")

    friendship = friend_service.send_request(
        db_session, requester_id=a.id, addressee_email="b@example.com"
    )

    assert friendship.status == FriendshipStatus.PENDING
    assert friendship.requester_id == a.id
    assert friendship.addressee_id == b.id


def test_cannot_friend_a_nonexistent_email(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    with pytest.raises(friend_service.UserNotFoundError):
        friend_service.send_request(
            db_session, requester_id=a.id, addressee_email="ghost@example.com"
        )


def test_cannot_friend_self(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    with pytest.raises(friend_service.CannotFriendSelfError):
        friend_service.send_request(db_session, requester_id=a.id, addressee_email="a@example.com")


def test_cannot_send_duplicate_request_in_either_direction(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    create_user(db_session, email="b@example.com")
    friend_service.send_request(db_session, requester_id=a.id, addressee_email="b@example.com")

    with pytest.raises(friend_service.FriendshipAlreadyExistsError):
        friend_service.send_request(db_session, requester_id=a.id, addressee_email="b@example.com")


def test_only_the_addressee_can_accept(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    create_user(db_session, email="b@example.com")
    friendship = friend_service.send_request(
        db_session, requester_id=a.id, addressee_email="b@example.com"
    )

    with pytest.raises(friend_service.NotAuthorizedError):
        friend_service.accept_request(db_session, user_id=a.id, friendship_id=friendship.id)


def test_accepting_makes_the_pair_mutual_friends(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    b = create_user(db_session, email="b@example.com")
    friendship = friend_service.send_request(
        db_session, requester_id=a.id, addressee_email="b@example.com"
    )
    friend_service.accept_request(db_session, user_id=b.id, friendship_id=friendship.id)

    assert {u.email for u in friend_service.list_friends(db_session, a.id)} == {"b@example.com"}
    assert {u.email for u in friend_service.list_friends(db_session, b.id)} == {"a@example.com"}


def test_declining_a_pending_request_removes_it(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    b = create_user(db_session, email="b@example.com")
    friendship = friend_service.send_request(
        db_session, requester_id=a.id, addressee_email="b@example.com"
    )
    friend_service.remove_or_decline(db_session, user_id=b.id, friendship_id=friendship.id)

    assert friend_service.list_friends(db_session, a.id) == []
    # Sending a new request afterward should work again (no leftover row).
    friend_service.send_request(db_session, requester_id=a.id, addressee_email="b@example.com")


def test_a_third_party_cannot_remove_someone_elses_friendship(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    create_user(db_session, email="b@example.com")
    outsider = create_user(db_session, email="c@example.com")
    friendship = friend_service.send_request(
        db_session, requester_id=a.id, addressee_email="b@example.com"
    )

    with pytest.raises(friend_service.NotAuthorizedError):
        friend_service.remove_or_decline(
            db_session, user_id=outsider.id, friendship_id=friendship.id
        )


def test_first_friend_achievement_unlocks_on_acceptance(db_session: Session) -> None:
    seed_achievement_catalog(db_session)
    a = create_user(db_session, email="a@example.com")
    b = create_user(db_session, email="b@example.com")
    friendship = friend_service.send_request(
        db_session, requester_id=a.id, addressee_email="b@example.com"
    )
    friend_service.accept_request(db_session, user_id=b.id, friendship_id=friendship.id)

    earned = {
        ua.achievement_id for ua in gamification_repository.get_user_achievements(db_session, a.id)
    }
    catalog = {ach.code: ach.id for ach in gamification_repository.list_achievements(db_session)}
    assert catalog["FIRST_FRIEND"] in earned


def test_friends_leaderboard_ranks_self_and_friends_by_this_weeks_xp(db_session: Session) -> None:
    a = create_user(db_session, email="a@example.com")
    b = create_user(db_session, email="b@example.com")
    outsider = create_user(db_session, email="c@example.com")
    friendship = friend_service.send_request(
        db_session, requester_id=a.id, addressee_email="b@example.com"
    )
    friend_service.accept_request(db_session, user_id=b.id, friendship_id=friendship.id)

    gamification_repository.record_xp_transaction(
        db_session,
        user_id=b.id,
        amount=40,
        reason=XPReason.LESSON_COMPLETED,
        lesson_attempt_id=None,
    )
    gamification_repository.record_xp_transaction(
        db_session,
        user_id=outsider.id,
        amount=1000,
        reason=XPReason.LESSON_COMPLETED,
        lesson_attempt_id=None,
    )
    db_session.commit()

    entries = friend_service.get_friends_leaderboard(db_session, a.id, datetime.now(UTC))
    emails = {e.email for e in entries}
    assert emails == {"a@example.com", "b@example.com"}  # outsider excluded
    assert entries[0].email == "b@example.com"  # ranked above self (0 XP)
