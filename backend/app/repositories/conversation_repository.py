import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationScenario,
    ConversationStatus,
    MessageRole,
)


def create_conversation(
    db: Session, *, user_id: uuid.UUID, scenario: ConversationScenario
) -> Conversation:
    conversation = Conversation(user_id=user_id, scenario=scenario)
    db.add(conversation)
    db.flush()
    return conversation


def get_conversation(db: Session, conversation_id: uuid.UUID) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    return db.execute(stmt).scalar_one_or_none()


def list_conversations_for_user(db: Session, user_id: uuid.UUID) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.started_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def add_message(
    db: Session, *, conversation_id: uuid.UUID, role: MessageRole, content: str
) -> ConversationMessage:
    message = ConversationMessage(conversation_id=conversation_id, role=role, content=content)
    db.add(message)
    db.flush()
    return message


def end_conversation(
    db: Session, *, conversation: Conversation, summary: str, ended_at: datetime
) -> Conversation:
    conversation.status = ConversationStatus.ENDED
    conversation.summary = summary
    conversation.ended_at = ended_at
    db.flush()
    return conversation
