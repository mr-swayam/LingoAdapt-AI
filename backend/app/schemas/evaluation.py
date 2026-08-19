import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.evaluation import DetectedError


class ErrorType(enum.StrEnum):
    GRAMMAR = "GRAMMAR"
    VOCABULARY = "VOCABULARY"
    SPELLING = "SPELLING"
    WORD_ORDER = "WORD_ORDER"
    OTHER = "OTHER"


class ErrorSeverity(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_TYPE_KEYWORDS: dict[str, ErrorType] = {
    "GRAMMAR": ErrorType.GRAMMAR,
    "VOCAB": ErrorType.VOCABULARY,
    "WORD ORDER": ErrorType.WORD_ORDER,
    "SPELL": ErrorType.SPELLING,
}

_SEVERITY_KEYWORDS: dict[str, ErrorSeverity] = {
    "HIGH": ErrorSeverity.HIGH,
    "MAJOR": ErrorSeverity.HIGH,
    "SEVERE": ErrorSeverity.HIGH,
    "LOW": ErrorSeverity.LOW,
    "MINOR": ErrorSeverity.LOW,
    "SLIGHT": ErrorSeverity.LOW,
}


def normalize_error_type(raw: str) -> ErrorType:
    """LLMs don't reliably match an exact enum vocabulary even when asked
    to. Keyword-matching against the model's free-text answer is more
    robust than hard-rejecting the whole response over casing/wording.
    """
    upper = raw.upper()
    for keyword, mapped in _TYPE_KEYWORDS.items():
        if keyword in upper:
            return mapped
    return ErrorType.OTHER


def normalize_severity(raw: str) -> ErrorSeverity:
    upper = raw.upper()
    for keyword, mapped in _SEVERITY_KEYWORDS.items():
        if keyword in upper:
            return mapped
    return ErrorSeverity.MEDIUM


class RawAIError(BaseModel):
    """The AI's error entry, before normalization - `type`/`severity` are
    plain strings here because we can't guarantee the model's casing."""

    type: str
    skill: str
    severity: str


class RawAIEvaluation(BaseModel):
    """What the AI actually returns. Structurally strict (rules.md: never
    trust AI output without validation) - unlike type/severity, is_correct,
    score, explanation, and corrected_answer are meaningless if malformed,
    so those fail validation outright rather than being normalized.
    """

    is_correct: bool
    score: float = Field(ge=0, le=1)
    errors: list[RawAIError] = Field(default_factory=list)
    explanation: str
    corrected_answer: str


class EvaluatedError(BaseModel):
    type: ErrorType
    skill: str
    severity: ErrorSeverity


class AIEvaluationResult(BaseModel):
    """The normalized result the rest of the app works with."""

    is_correct: bool
    score: float
    errors: list[EvaluatedError]
    explanation: str
    corrected_answer: str

    @classmethod
    def from_raw(cls, raw: RawAIEvaluation) -> "AIEvaluationResult":
        return cls(
            is_correct=raw.is_correct,
            score=raw.score,
            errors=[
                EvaluatedError(
                    type=normalize_error_type(e.type),
                    skill=e.skill,
                    severity=normalize_severity(e.severity),
                )
                for e in raw.errors
            ],
            explanation=raw.explanation,
            corrected_answer=raw.corrected_answer,
        )


class DetectedErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    error_type: ErrorType
    severity: ErrorSeverity
    description: str
    submitted_text: str
    created_at: datetime

    @classmethod
    def from_model(cls, row: DetectedError) -> "DetectedErrorOut":
        return cls(
            id=row.id,
            error_type=ErrorType(row.error_type.value),
            severity=ErrorSeverity(row.severity.value),
            description=row.description,
            submitted_text=row.submitted_text,
            created_at=row.created_at,
        )
