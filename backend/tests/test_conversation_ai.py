import pytest

from app.ai.exceptions import AIRequestError, AIResponseValidationError, AITimeoutError
from app.models.conversation import ConversationScenario
from app.services.conversation_ai import generate_turn
from app.services.learner_context import LearnerContext
from tests.ai_fixtures import FakeAIProvider

_CONTEXT = LearnerContext(
    target_language="English",
    estimated_level="A2",
    current_topic="Restaurant",
    weak_skills=["PAST_TENSE"],
    strong_skills=["FOOD_VOCABULARY"],
    recent_errors=["go/went"],
)


@pytest.mark.asyncio
async def test_successful_turn_parses_and_validates() -> None:
    provider = FakeAIProvider()
    provider.queue_conversation_turn(reply="Welcome! What would you like to order?")

    turn = await generate_turn(
        provider,
        scenario=ConversationScenario.RESTAURANT,
        context=_CONTEXT,
        history=[],
        learner_message="Hello",
    )

    assert turn.reply == "Welcome! What would you like to order?"
    assert turn.corrections == []


@pytest.mark.asyncio
async def test_corrections_skill_normalized_despite_odd_casing() -> None:
    provider = FakeAIProvider()
    provider.queue_conversation_turn(
        reply="Got it, thanks!",
        corrections=[
            {
                "original": "I go there yesterday",
                "corrected": "I went there yesterday",
                "explanation": "Use past tense for completed actions.",
                "skill": "past tense verb",
            },
            {
                "original": "informations",
                "corrected": "information",
                "explanation": "Uncountable noun.",
                "skill": "something unrecognized",
            },
        ],
    )

    turn = await generate_turn(
        provider,
        scenario=ConversationScenario.RESTAURANT,
        context=_CONTEXT,
        history=[],
        learner_message="I go there yesterday",
    )

    assert turn.corrections[0].skill.value == "PAST_TENSE"
    assert turn.corrections[1].skill.value == "GENERAL"  # unrecognized -> GENERAL default


@pytest.mark.asyncio
async def test_malformed_json_raises_validation_error() -> None:
    provider = FakeAIProvider()
    provider.queue_raw_content("not valid json")

    with pytest.raises(AIResponseValidationError):
        await generate_turn(
            provider,
            scenario=ConversationScenario.CASUAL,
            context=_CONTEXT,
            history=[],
            learner_message="hi",
        )


@pytest.mark.asyncio
async def test_missing_reply_field_raises_validation_error() -> None:
    provider = FakeAIProvider()
    provider.queue_raw_content('{"corrections": []}')

    with pytest.raises(AIResponseValidationError):
        await generate_turn(
            provider,
            scenario=ConversationScenario.CASUAL,
            context=_CONTEXT,
            history=[],
            learner_message="hi",
        )


@pytest.mark.asyncio
async def test_empty_reply_raises_validation_error() -> None:
    provider = FakeAIProvider()
    provider.queue_raw_content('{"reply": "", "corrections": []}')

    with pytest.raises(AIResponseValidationError):
        await generate_turn(
            provider,
            scenario=ConversationScenario.CASUAL,
            context=_CONTEXT,
            history=[],
            learner_message="hi",
        )


@pytest.mark.asyncio
async def test_provider_timeout_propagates() -> None:
    provider = FakeAIProvider()
    provider.queue_timeout()

    with pytest.raises(AITimeoutError):
        await generate_turn(
            provider,
            scenario=ConversationScenario.CASUAL,
            context=_CONTEXT,
            history=[],
            learner_message="hi",
        )


@pytest.mark.asyncio
async def test_provider_request_error_propagates() -> None:
    provider = FakeAIProvider()
    provider.queue_request_error()

    with pytest.raises(AIRequestError):
        await generate_turn(
            provider,
            scenario=ConversationScenario.CASUAL,
            context=_CONTEXT,
            history=[],
            learner_message="hi",
        )
