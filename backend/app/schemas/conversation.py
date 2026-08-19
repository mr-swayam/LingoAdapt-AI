import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationScenario,
    ConversationStatus,
    MessageRole,
)


class ConversationSkill(enum.StrEnum):
    """Mirrors app.seed.GRAMMAR_SKILLS' codes - the vocabulary conversation
    corrections resolve to a skill_id against."""

    PAST_TENSE = "PAST_TENSE"
    PREPOSITIONS = "PREPOSITIONS"
    ARTICLES = "ARTICLES"
    SUBJECT_VERB_AGREEMENT = "SUBJECT_VERB_AGREEMENT"
    PLURALS = "PLURALS"
    WORD_CHOICE = "WORD_CHOICE"
    GENERAL = "GENERAL"


_SKILL_KEYWORDS: dict[str, ConversationSkill] = {
    "PAST": ConversationSkill.PAST_TENSE,
    "TENSE": ConversationSkill.PAST_TENSE,
    "PREPOSITION": ConversationSkill.PREPOSITIONS,
    "ARTICLE": ConversationSkill.ARTICLES,
    "AGREEMENT": ConversationSkill.SUBJECT_VERB_AGREEMENT,
    "SUBJECT": ConversationSkill.SUBJECT_VERB_AGREEMENT,
    "VERB": ConversationSkill.SUBJECT_VERB_AGREEMENT,
    "PLURAL": ConversationSkill.PLURALS,
    "WORD CHOICE": ConversationSkill.WORD_CHOICE,
    "VOCAB": ConversationSkill.WORD_CHOICE,
}


def normalize_skill(raw: str) -> ConversationSkill:
    """Same rationale as schemas.evaluation.normalize_error_type: LLMs don't
    reliably match an exact enum vocabulary, so keyword-match the model's
    free text rather than hard-rejecting the whole turn."""
    upper = raw.upper()
    for keyword, mapped in _SKILL_KEYWORDS.items():
        if keyword in upper:
            return mapped
    return ConversationSkill.GENERAL


class RawAICorrection(BaseModel):
    """`skill` is a plain string here because we can't guarantee the model's
    casing/wording - original/corrected/explanation are meaningless if
    malformed, so those fail validation outright rather than being
    normalized."""

    original: str
    corrected: str
    explanation: str
    skill: str


class RawAIConversationTurn(BaseModel):
    """What the AI actually returns for one conversation turn. Structurally
    strict (rules.md: never trust AI output without validation)."""

    reply: str = Field(min_length=1)
    corrections: list[RawAICorrection] = Field(default_factory=list)


class ConversationCorrection(BaseModel):
    original: str
    corrected: str
    explanation: str
    skill: ConversationSkill


class AIConversationTurn(BaseModel):
    """The normalized result the rest of the app works with."""

    reply: str
    corrections: list[ConversationCorrection]

    @classmethod
    def from_raw(cls, raw: RawAIConversationTurn) -> "AIConversationTurn":
        return cls(
            reply=raw.reply,
            corrections=[
                ConversationCorrection(
                    original=c.original,
                    corrected=c.corrected,
                    explanation=c.explanation,
                    skill=normalize_skill(c.skill),
                )
                for c in raw.corrections
            ],
        )


class ConversationMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime

    @classmethod
    def from_model(cls, row: ConversationMessage) -> "ConversationMessageOut":
        return cls(id=row.id, role=row.role, content=row.content, created_at=row.created_at)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scenario: ConversationScenario
    status: ConversationStatus
    summary: str | None
    started_at: datetime
    ended_at: datetime | None

    @classmethod
    def from_model(cls, row: Conversation) -> "ConversationOut":
        return cls(
            id=row.id,
            scenario=row.scenario,
            status=row.status,
            summary=row.summary,
            started_at=row.started_at,
            ended_at=row.ended_at,
        )


class ConversationDetailOut(ConversationOut):
    messages: list[ConversationMessageOut]

    @classmethod
    def from_model_with_messages(cls, row: Conversation) -> "ConversationDetailOut":
        return cls(
            id=row.id,
            scenario=row.scenario,
            status=row.status,
            summary=row.summary,
            started_at=row.started_at,
            ended_at=row.ended_at,
            messages=[ConversationMessageOut.from_model(m) for m in row.messages],
        )


class StartConversationRequest(BaseModel):
    scenario: ConversationScenario


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class CorrectionOut(BaseModel):
    original: str
    corrected: str
    explanation: str
    skill: ConversationSkill


class SendMessageResponse(BaseModel):
    learner_message: ConversationMessageOut
    tutor_message: ConversationMessageOut
    corrections: list[CorrectionOut]


class VoiceSendMessageResponse(SendMessageResponse):
    """Same shape as SendMessageResponse, plus the AI-transcribed text
    (Phase 8 voice conversation)."""

    transcript: str
