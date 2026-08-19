import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import TZ_DATETIME, Base


class ConversationScenario(enum.StrEnum):
    RESTAURANT = "RESTAURANT"
    AIRPORT = "AIRPORT"
    JOB_INTERVIEW = "JOB_INTERVIEW"
    SHOPPING = "SHOPPING"
    CASUAL = "CASUAL"
    COLLEGE = "COLLEGE"
    TRAVEL = "TRAVEL"


class ConversationStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class MessageRole(enum.StrEnum):
    LEARNER = "LEARNER"
    TUTOR = "TUTOR"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario: Mapped[ConversationScenario] = mapped_column(
        Enum(ConversationScenario, name="conversation_scenario", native_enum=True),
        nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status", native_enum=True),
        nullable=False,
        default=ConversationStatus.ACTIVE,
    )
    # Populated deterministically when the conversation ends (memory.md §2E:
    # "Summary" - not AI-generated, per rules.md §2.6 "avoid unnecessary AI
    # calls" for something derivable locally).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME, nullable=True)

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", native_enum=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZ_DATETIME, server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
