import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TZ_DATETIME, Base


class FriendshipStatus(enum.StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class Friendship(Base):
    """A directed request (requester -> addressee) that becomes a symmetric
    relationship once accepted. app/services/friend_service.py checks both
    directions before creating a new row, so a pair of users is represented
    by at most one row regardless of who sent the request.
    """

    __tablename__ = "friendships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, name="friendship_status", native_enum=True),
        nullable=False,
        default=FriendshipStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)

    __table_args__ = (
        CheckConstraint("requester_id != addressee_id", name="ck_friendship_not_self"),
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )
