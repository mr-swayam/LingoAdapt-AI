import pytest

from app.ai.exceptions import AIRequestError, AIResponseValidationError, AITimeoutError
from app.services.evaluation_service import evaluate_free_response
from tests.ai_fixtures import FakeAIProvider


@pytest.mark.asyncio
async def test_successful_evaluation_parses_and_validates() -> None:
    provider = FakeAIProvider()
    provider.queue_evaluation(
        is_correct=True,
        score=0.95,
        explanation="Well done.",
        corrected_answer="My name is Anna.",
    )

    result = await evaluate_free_response(
        provider,
        prompt="Introduce yourself.",
        model_answer="My name is X.",
        rubric="Should include a name.",
        submitted_text="My name is Anna.",
    )

    assert result.is_correct is True
    assert result.score == 0.95
    assert result.explanation == "Well done."


@pytest.mark.asyncio
async def test_errors_are_normalized_despite_odd_casing() -> None:
    provider = FakeAIProvider()
    provider.queue_evaluation(
        is_correct=False,
        score=0.2,
        errors=[
            {"type": "grammar", "skill": "verb usage", "severity": "major"},
            {"type": "totally unknown category", "skill": "x", "severity": "meh"},
        ],
    )

    result = await evaluate_free_response(
        provider, prompt="p", model_answer="m", rubric="r", submitted_text="s"
    )

    assert result.errors[0].type.value == "GRAMMAR"
    assert result.errors[0].severity.value == "HIGH"  # "major" -> HIGH
    assert result.errors[1].type.value == "OTHER"  # unrecognized -> OTHER
    assert result.errors[1].severity.value == "MEDIUM"  # unrecognized -> MEDIUM default


@pytest.mark.asyncio
async def test_malformed_json_raises_validation_error() -> None:
    provider = FakeAIProvider()
    provider.queue_raw_content("not valid json at all")

    with pytest.raises(AIResponseValidationError):
        await evaluate_free_response(
            provider, prompt="p", model_answer="m", rubric="r", submitted_text="s"
        )


@pytest.mark.asyncio
async def test_missing_required_field_raises_validation_error() -> None:
    provider = FakeAIProvider()
    provider.queue_raw_content('{"is_correct": true}')  # missing score/explanation/etc.

    with pytest.raises(AIResponseValidationError):
        await evaluate_free_response(
            provider, prompt="p", model_answer="m", rubric="r", submitted_text="s"
        )


@pytest.mark.asyncio
async def test_score_out_of_range_raises_validation_error() -> None:
    provider = FakeAIProvider()
    provider.queue_raw_content(
        '{"is_correct": true, "score": 1.5, "errors": [], "explanation": "x", '
        '"corrected_answer": "y"}'
    )

    with pytest.raises(AIResponseValidationError):
        await evaluate_free_response(
            provider, prompt="p", model_answer="m", rubric="r", submitted_text="s"
        )


@pytest.mark.asyncio
async def test_provider_timeout_propagates() -> None:
    provider = FakeAIProvider()
    provider.queue_timeout()

    with pytest.raises(AITimeoutError):
        await evaluate_free_response(
            provider, prompt="p", model_answer="m", rubric="r", submitted_text="s"
        )


@pytest.mark.asyncio
async def test_provider_request_error_propagates() -> None:
    provider = FakeAIProvider()
    provider.queue_request_error()

    with pytest.raises(AIRequestError):
        await evaluate_free_response(
            provider, prompt="p", model_answer="m", rubric="r", submitted_text="s"
        )
