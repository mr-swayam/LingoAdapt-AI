import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import TZ_DATETIME, Base


class XPReason(enum.StrEnum):
    LESSON_COMPLETED = "LESSON_COMPLETED"


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[XPReason] = mapped_column(
        Enum(XPReason, name="xp_reason", native_enum=True), nullable=False
    )
    lesson_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lesson_attempts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # DB-level guard against double-awarding the same lesson completion,
        # even under concurrent requests - app-level idempotency checks alone
        # can race.
        UniqueConstraint(
            "lesson_attempt_id", "reason", name="uq_xp_transaction_attempt_reason"
        ),
    )


class Streak(Base):
    __tablename__ = "streaks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    earned_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )

    achievement: Mapped["Achievement"] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)


class LeagueTier(enum.StrEnum):
    """Ordered lowest-to-highest - app/services/league_service.py relies on
    this exact declaration order for promotion/demotion index math."""

    SPARK = "SPARK"
    EMBER = "EMBER"
    BLAZE = "BLAZE"
    AURORA = "AURORA"
    ZENITH = "ZENITH"


class UserLeague(Base):
    """One row per user: their current league tier and the start-of-week
    their `week_start`-scoped cohort is measured from. Promotion/demotion is
    computed lazily (app/services/league_service.py) rather than via a
    scheduled job - this project has no background-job runner yet - so
    `week_start` intentionally lags for inactive users until they're next
    read/written, at which point their finished week is scored against
    whichever tier-mates share that same (now-stale) `week_start`.
    """

    __tablename__ = "user_leagues"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tier: Mapped[LeagueTier] = mapped_column(
        Enum(LeagueTier, name="league_tier", native_enum=True),
        nullable=False,
        default=LeagueTier.SPARK,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QuestType(enum.StrEnum):
    EARN_XP = "EARN_XP"
    COMPLETE_LESSON = "COMPLETE_LESSON"
    PRACTICE_SESSION = "PRACTICE_SESSION"


class DailyQuest(Base):
    """One row per (user, date, quest_type) - app/services/quest_service.py
    generates the day's quests idempotently and computes `progress` live
    from existing learning-event data (xp_transactions, lesson_attempts,
    practice_sessions) rather than maintaining a separately-mutated
    counter, matching how xp_today/streaks are already computed elsewhere
    in this codebase.
    """

    __tablename__ = "daily_quests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quest_date: Mapped[date] = mapped_column(Date, nullable=False)
    quest_type: Mapped[QuestType] = mapped_column(
        Enum(QuestType, name="quest_type", native_enum=True), nullable=False
    )
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_gems: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "quest_date", "quest_type", name="uq_daily_quest_user_date_type"
        ),
    )


class CurrencyReason(enum.StrEnum):
    QUEST_COMPLETED = "QUEST_COMPLETED"
    ACHIEVEMENT_UNLOCKED = "ACHIEVEMENT_UNLOCKED"
    LEAGUE_PROMOTION = "LEAGUE_PROMOTION"


class CurrencyTransaction(Base):
    """Gems - a virtual currency awarded only for meaningful milestones
    (quest completion, achievement unlocks, league promotion), never for
    raw activity, per rules.md §8.2 ("do not reward meaningless button
    clicking"). `source_id` is a polymorphic reference (a quest id,
    user_achievement id, or league-promotion event key) rather than an FK,
    since it points at different tables depending on `reason` - the
    uniqueness constraint on (source_id, reason) is what actually prevents
    double-awarding, matching XPTransaction's equivalent guard.
    """

    __tablename__ = "currency_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[CurrencyReason] = mapped_column(
        Enum(CurrencyReason, name="currency_reason", native_enum=True), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_currency_transaction_amount_positive"),
        UniqueConstraint("source_id", "reason", name="uq_currency_transaction_source_reason"),
    )
