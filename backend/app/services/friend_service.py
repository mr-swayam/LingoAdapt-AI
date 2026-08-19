import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.social import Friendship, FriendshipStatus
from app.models.user import User
from app.repositories import gamification_repository, social_repository, user_repository
from app.services import gamification_service
from app.services.league_service import LeaderboardEntry, current_week_start


class FriendServiceError(Exception):
    pass


class UserNotFoundError(FriendServiceError):
    pass


class CannotFriendSelfError(FriendServiceError):
    pass


class FriendshipAlreadyExistsError(FriendServiceError):
    pass


class FriendshipNotFoundError(FriendServiceError):
    pass


class NotAuthorizedError(FriendServiceError):
    pass


def send_request(db: Session, *, requester_id: uuid.UUID, addressee_email: str) -> Friendship:
    addressee = user_repository.get_by_email(db, addressee_email)
    if addressee is None:
        raise UserNotFoundError(addressee_email)
    if addressee.id == requester_id:
        raise CannotFriendSelfError(requester_id)
    if social_repository.get_friendship_between(db, requester_id, addressee.id) is not None:
        raise FriendshipAlreadyExistsError((requester_id, addressee.id))

    friendship = social_repository.create_friendship(
        db, requester_id=requester_id, addressee_id=addressee.id
    )
    db.commit()
    return friendship


def accept_request(db: Session, *, user_id: uuid.UUID, friendship_id: uuid.UUID) -> Friendship:
    friendship = social_repository.get_friendship_by_id(db, friendship_id)
    if friendship is None:
        raise FriendshipNotFoundError(friendship_id)
    if friendship.addressee_id != user_id:
        raise NotAuthorizedError(user_id)
    if friendship.status != FriendshipStatus.PENDING:
        return friendship

    updated = social_repository.update_friendship_status(
        db, friendship=friendship, status=FriendshipStatus.ACCEPTED, responded_at=datetime.now(UTC)
    )
    # Both sides just gained a friend - check achievements for each.
    gamification_service.evaluate_achievements_for_user(db, friendship.requester_id)
    gamification_service.evaluate_achievements_for_user(db, friendship.addressee_id)
    db.commit()
    return updated


def remove_or_decline(db: Session, *, user_id: uuid.UUID, friendship_id: uuid.UUID) -> None:
    friendship = social_repository.get_friendship_by_id(db, friendship_id)
    if friendship is None:
        raise FriendshipNotFoundError(friendship_id)
    if user_id not in (friendship.requester_id, friendship.addressee_id):
        raise NotAuthorizedError(user_id)

    social_repository.delete_friendship(db, friendship)
    db.commit()


def _other_user_id(friendship: Friendship, user_id: uuid.UUID) -> uuid.UUID:
    if friendship.requester_id == user_id:
        return friendship.addressee_id
    return friendship.requester_id


def list_friends(db: Session, user_id: uuid.UUID) -> list[User]:
    friendships = social_repository.list_accepted_friendships(db, user_id)
    friends = []
    for friendship in friendships:
        other = user_repository.get_by_id(db, _other_user_id(friendship, user_id))
        if other is not None:
            friends.append(other)
    return friends


@dataclass(frozen=True)
class PendingRequest:
    friendship_id: uuid.UUID
    other_user_email: str
    created_at: datetime


def list_pending_incoming(db: Session, user_id: uuid.UUID) -> list[PendingRequest]:
    result = []
    for friendship in social_repository.list_pending_incoming(db, user_id):
        requester = user_repository.get_by_id(db, friendship.requester_id)
        if requester is not None:
            result.append(
                PendingRequest(
                    friendship_id=friendship.id,
                    other_user_email=requester.email,
                    created_at=friendship.created_at,
                )
            )
    return result


def list_pending_outgoing(db: Session, user_id: uuid.UUID) -> list[PendingRequest]:
    result = []
    for friendship in social_repository.list_pending_outgoing(db, user_id):
        addressee = user_repository.get_by_id(db, friendship.addressee_id)
        if addressee is not None:
            result.append(
                PendingRequest(
                    friendship_id=friendship.id,
                    other_user_email=addressee.email,
                    created_at=friendship.created_at,
                )
            )
    return result


def get_friends_leaderboard(
    db: Session, user_id: uuid.UUID, now: datetime
) -> list[LeaderboardEntry]:
    """Ranks the learner against their accepted friends by this calendar
    week's XP - no cohort/promotion state to track (unlike leagues), so
    it's always computed fresh from the current week."""
    me = user_repository.get_by_id(db, user_id)
    if me is None:
        return []

    friends = list_friends(db, user_id)
    users_by_id: dict[uuid.UUID, User] = {user_id: me, **{f.id: f for f in friends}}
    xp_by_user = gamification_repository.get_weekly_xp_for_users(
        db,
        list(users_by_id.keys()),
        since=datetime.combine(current_week_start(now), datetime.min.time(), tzinfo=UTC),
        until=now,
    )
    ranked = sorted(xp_by_user.items(), key=lambda pair: (-pair[1], pair[0].hex))

    return [
        LeaderboardEntry(
            user_id=uid,
            email=users_by_id[uid].email,
            weekly_xp=xp,
            rank=i + 1,
            is_me=uid == user_id,
        )
        for i, (uid, xp) in enumerate(ranked)
        if uid in users_by_id
    ]
