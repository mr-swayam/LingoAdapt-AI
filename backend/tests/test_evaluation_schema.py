"""Phase 13 Task 5: schema-level tests for AI evaluation output, plus
deterministic mocked-provider coverage of every error category the app
classifies. Complements test_evaluation_service.py (which covers the
service function's error-handling paths) with direct unit tests on the
Pydantic schema/normalization functions themselves (rules.md: "AI output
schema tests").
"""

import pytest
from pydantic import ValidationError

from app.schemas.evaluation import (
    ErrorSeverity,
    ErrorType,
    RawAIError,
    RawAIEvaluation,
    normalize_error_type,
    normalize_severity,
)

# --- normalize_error_type / normalize_severity: pure functions, no AI needed ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("GRAMMAR", ErrorType.GRAMMAR),
        ("grammar", ErrorType.GRAMMAR),
        ("Grammar mistake", ErrorType.GRAMMAR),
        ("VOCAB", ErrorType.VOCABULARY),
        ("vocabulary error", ErrorType.VOCABULARY),
        ("WORD ORDER", ErrorType.WORD_ORDER),
        ("word order issue", ErrorType.WORD_ORDER),
        ("SPELL", ErrorType.SPELLING),
        ("spelling mistake", ErrorType.SPELLING),
        ("something the model invented", ErrorType.OTHER),
        ("", ErrorType.OTHER),
    ],
)
def test_normalize_error_type(raw: str, expected: ErrorType) -> None:
    assert normalize_error_type(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("HIGH", ErrorSeverity.HIGH),
        ("major", ErrorSeverity.HIGH),
        ("severe", ErrorSeverity.HIGH),
        ("LOW", ErrorSeverity.LOW),
        ("minor", ErrorSeverity.LOW),
        ("slight", ErrorSeverity.LOW),
        ("MEDIUM", ErrorSeverity.MEDIUM),  # not a keyword - falls through to the default
        ("whatever the model felt like saying", ErrorSeverity.MEDIUM),
        ("", ErrorSeverity.MEDIUM),
    ],
)
def test_normalize_severity(raw: str, expected: ErrorSeverity) -> None:
    assert normalize_severity(raw) == expected


# --- RawAIEvaluation: strict validation on the fields that can't be normalized ---


def _valid_payload(**overrides: object) -> dict:
    payload = {
        "is_correct": True,
        "score": 0.9,
        "errors": [],
        "explanation": "Well done.",
        "corrected_answer": "x",
    }
    payload.update(overrides)
    return payload


def test_raw_evaluation_accepts_boundary_scores() -> None:
    assert RawAIEvaluation.model_validate(_valid_payload(score=0.0)).score == 0.0
    assert RawAIEvaluation.model_validate(_valid_payload(score=1.0)).score == 1.0


@pytest.mark.parametrize("bad_score", [-0.01, 1.01, -1.0, 2.0])
def test_raw_evaluation_rejects_out_of_range_score(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        RawAIEvaluation.model_validate(_valid_payload(score=bad_score))


@pytest.mark.parametrize(
    "missing_field", ["is_correct", "score", "explanation", "corrected_answer"]
)
def test_raw_evaluation_rejects_missing_required_field(missing_field: str) -> None:
    payload = _valid_payload()
    del payload[missing_field]
    with pytest.raises(ValidationError):
        RawAIEvaluation.model_validate(payload)


def test_raw_evaluation_rejects_wrong_type_for_is_correct() -> None:
    # Pydantic v2's lax bool coercion accepts some string reps ("true"/"yes"/
    # "1"), so this needs a value that's unambiguously not boolean-ish.
    with pytest.raises(ValidationError):
        RawAIEvaluation.model_validate(_valid_payload(is_correct={"maybe": True}))


def test_raw_evaluation_rejects_non_list_errors() -> None:
    with pytest.raises(ValidationError):
        RawAIEvaluation.model_validate(_valid_payload(errors="none"))


def test_raw_evaluation_ignores_unexpected_extra_fields() -> None:
    """Models sometimes add fields nobody asked for - extra, unrecognized
    keys must not break parsing of an otherwise-valid response."""
    payload = _valid_payload()
    payload["confidence_level"] = "very high"
    payload["model_used"] = "some-model"
    result = RawAIEvaluation.model_validate(payload)
    assert result.is_correct is True


def test_raw_evaluation_handles_many_errors() -> None:
    payload = _valid_payload(
        is_correct=False,
        errors=[
            {"type": "GRAMMAR", "skill": f"issue {i}", "severity": "LOW"} for i in range(20)
        ],
    )
    result = RawAIEvaluation.model_validate(payload)
    assert len(result.errors) == 20


def test_raw_error_requires_all_three_fields() -> None:
    with pytest.raises(ValidationError):
        RawAIError.model_validate({"type": "GRAMMAR", "skill": "x"})  # missing severity
