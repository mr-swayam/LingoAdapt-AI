import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.social import Friendship, FriendshipStatus


def get_friendship_between(
    db: Session, user_a: uuid.UUID, user_b: uuid.UUID
) -> Friendship | None:
    """Regardless of who originally sent the request."""
    stmt = select(Friendship).where(
        or_(
            (Friendship.requester_id == user_a) & (Friendship.addressee_id == user_b),
            (Friendship.requester_id == user_b) & (Friendship.addressee_id == user_a),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_friendship_by_id(db: Session, friendship_id: uuid.UUID) -> Friendship | None:
    return db.get(Friendship, friendship_id)


def create_friendship(
    db: Session, *, requester_id: uuid.UUID, addressee_id: uuid.UUID
) -> Friendship:
    friendship = Friendship(requester_id=requester_id, addressee_id=addressee_id)
    db.add(friendship)
    db.flush()
    return friendship


def update_friendship_status(
    db: Session, *, friendship: Friendship, status: FriendshipStatus, responded_at: datetime
) -> Friendship:
    friendship.status = status
    friendship.responded_at = responded_at
    db.flush()
    return friendship


def delete_friendship(db: Session, friendship: Friendship) -> None:
    db.delete(friendship)
    db.flush()


def list_accepted_friendships(db: Session, user_id: uuid.UUID) -> list[Friendship]:
    stmt = select(Friendship).where(
        Friendship.status == FriendshipStatus.ACCEPTED,
        or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
    )
    return list(db.execute(stmt).scalars().all())


def list_pending_incoming(db: Session, user_id: uuid.UUID) -> list[Friendship]:
    stmt = select(Friendship).where(
        Friendship.addressee_id == user_id, Friendship.status == FriendshipStatus.PENDING
    )
    return list(db.execute(stmt).scalars().all())


def list_pending_outgoing(db: Session, user_id: uuid.UUID) -> list[Friendship]:
    stmt = select(Friendship).where(
        Friendship.requester_id == user_id, Friendship.status == FriendshipStatus.PENDING
    )
    return list(db.execute(stmt).scalars().all())


def count_accepted_friends(db: Session, user_id: uuid.UUID) -> int:
    return len(list_accepted_friendships(db, user_id))
