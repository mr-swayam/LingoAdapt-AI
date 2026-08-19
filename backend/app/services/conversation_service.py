import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.exceptions import AIProviderNotConfiguredError
from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationScenario,
    ConversationStatus,
    MessageRole,
)
from app.models.evaluation import DetectedErrorSeverity, DetectedErrorType
from app.repositories import conversation_repository, course_repository, evaluation_repository
from app.schemas.conversation import AIConversationTurn, ConversationCorrection, ConversationSkill
from app.services import conversation_ai, learner_context, learner_model_service

# Corrections aren't given an AI-assessed severity (unlike free-response
# grading) - there's no reliable signal for it in a conversational aside,
# so every conversation correction is treated as a routine, equal-weight
# MEDIUM note rather than guessing.
_CORRECTION_SEVERITY = DetectedErrorSeverity.MEDIUM

_SKILL_TO_ERROR_TYPE: dict[ConversationSkill, DetectedErrorType] = {
    ConversationSkill.PAST_TENSE: DetectedErrorType.GRAMMAR,
    ConversationSkill.PREPOSITIONS: DetectedErrorType.GRAMMAR,
    ConversationSkill.ARTICLES: DetectedErrorType.GRAMMAR,
    ConversationSkill.SUBJECT_VERB_AGREEMENT: DetectedErrorType.GRAMMAR,
    ConversationSkill.PLURALS: DetectedErrorType.GRAMMAR,
    ConversationSkill.WORD_CHOICE: DetectedErrorType.VOCABULARY,
    ConversationSkill.GENERAL: DetectedErrorType.OTHER,
}

# description column is String(200) - AI explanations are usually short but
# not guaranteed to be, so this is a boundary truncation, not app logic.
_DESCRIPTION_MAX_LEN = 200


class ConversationServiceError(Exception):
    pass


class ConversationNotFoundError(ConversationServiceError):
    pass


class ConversationNotOwnedError(ConversationServiceError):
    pass


class ConversationNotActiveError(ConversationServiceError):
    pass


def _get_owned_active_conversation(
    db: Session, *, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conversation = conversation_repository.get_conversation(db, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(conversation_id)
    if conversation.user_id != user_id:
        raise ConversationNotOwnedError(conversation_id)
    if conversation.status != ConversationStatus.ACTIVE:
        raise ConversationNotActiveError(conversation_id)
    return conversation


def start_conversation(
    db: Session, *, user_id: uuid.UUID, scenario: ConversationScenario
) -> Conversation:
    conversation = conversation_repository.create_conversation(
        db, user_id=user_id, scenario=scenario
    )
    db.commit()
    return conversation


def list_conversations(db: Session, *, user_id: uuid.UUID) -> list[Conversation]:
    return conversation_repository.list_conversations_for_user(db, user_id)


def get_conversation(
    db: Session, *, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conversation = conversation_repository.get_conversation(db, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(conversation_id)
    if conversation.user_id != user_id:
        raise ConversationNotOwnedError(conversation_id)
    return conversation


def _record_correction(
    db: Session,
    *,
    user_id: uuid.UUID,
    conversation_message_id: uuid.UUID,
    correction: ConversationCorrection,
) -> None:
    skill_row = course_repository.get_skill_by_code(db, correction.skill.value)
    if skill_row is None:
        # Catalog is seeded idempotently at deploy time (app/seed.py) - if
        # it's somehow missing, drop this one correction rather than fail
        # the whole turn the learner is waiting on.
        return

    evaluation_repository.record_detected_error(
        db,
        user_id=user_id,
        skill_id=skill_row.id,
        error_type=_SKILL_TO_ERROR_TYPE[correction.skill],
        severity=_CORRECTION_SEVERITY,
        description=correction.explanation[:_DESCRIPTION_MAX_LEN],
        submitted_text=correction.original,
        conversation_message_id=conversation_message_id,
    )
    learner_model_service.record_conversation_mistake(
        db,
        user_id=user_id,
        skill_id=skill_row.id,
        conversation_message_id=conversation_message_id,
    )


@dataclass(frozen=True)
class SendMessageResult:
    learner_message: ConversationMessage
    tutor_message: ConversationMessage
    corrections: list[ConversationCorrection]


async def send_message(
    db: Session,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    text: str,
    ai_provider: AIProvider | None,
) -> SendMessageResult:
    if ai_provider is None:
        raise AIProviderNotConfiguredError

    conversation = _get_owned_active_conversation(
        db, user_id=user_id, conversation_id=conversation_id
    )
    history = list(conversation.messages)

    context = learner_context.build_learner_context(
        db, user_id=user_id, scenario=conversation.scenario
    )

    # AIProviderError/AIResponseValidationError propagate as-is here, before
    # anything is written - rules.md: "AI failure must not corrupt learning
    # state". The learner's text isn't persisted until the AI call succeeds,
    # so a failed turn leaves no trace (matches ai_grading.py's pattern).
    turn: AIConversationTurn = await conversation_ai.generate_turn(
        ai_provider,
        scenario=conversation.scenario,
        context=context,
        history=history,
        learner_message=text,
    )

    learner_msg = conversation_repository.add_message(
        db, conversation_id=conversation.id, role=MessageRole.LEARNER, content=text
    )
    tutor_msg = conversation_repository.add_message(
        db, conversation_id=conversation.id, role=MessageRole.TUTOR, content=turn.reply
    )

    for correction in turn.corrections:
        _record_correction(
            db,
            user_id=user_id,
            conversation_message_id=learner_msg.id,
            correction=correction,
        )

    db.commit()

    return SendMessageResult(
        learner_message=learner_msg,
        tutor_message=tutor_msg,
        corrections=turn.corrections,
    )


def _build_summary(conversation: Conversation) -> str:
    """Deterministic, not AI-generated (models.conversation.Conversation's
    docstring / rules.md §2.6: avoid unnecessary AI calls for something
    derivable locally)."""
    message_count = len(conversation.messages)
    learner_turns = sum(1 for m in conversation.messages if m.role == MessageRole.LEARNER)
    scenario_label = conversation.scenario.value.replace("_", " ").title()

    if learner_turns == 0:
        return f"{scenario_label} conversation ended with no messages exchanged."

    return (
        f"{scenario_label} conversation: {learner_turns} learner message"
        f"{'s' if learner_turns != 1 else ''} ({message_count} total)."
    )


def end_conversation(
    db: Session, *, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conversation = _get_owned_active_conversation(
        db, user_id=user_id, conversation_id=conversation_id
    )
    summary = _build_summary(conversation)
    conversation_repository.end_conversation(
        db, conversation=conversation, summary=summary, ended_at=datetime.now(UTC)
    )
    db.commit()
    return conversation
