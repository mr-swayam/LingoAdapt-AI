import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.exceptions import AIRequestError, AITimeoutError
from app.ai.metering import MeteredAIProvider
from app.models.analytics import AiCallLog, AiCallOperation
from tests.ai_fixtures import FakeAIProvider
from tests.auth_fixtures import create_user


def _all_logs(db: Session) -> list[AiCallLog]:
    return list(db.execute(select(AiCallLog)).scalars().all())


@pytest.mark.asyncio
async def test_successful_chat_call_is_logged(db_session: Session) -> None:
    fake = FakeAIProvider()
    fake.queue_conversation_turn(reply="hi")
    user_id = create_user(db_session, email="metering1@example.com").id
    metered = MeteredAIProvider(fake, db=db_session, user_id=user_id, provider_name="groq")

    await metered.chat([])

    logs = _all_logs(db_session)
    assert len(logs) == 1
    assert logs[0].operation == AiCallOperation.CHAT
    assert logs[0].success is True
    assert logs[0].user_id == user_id
    assert logs[0].provider == "groq"
    assert logs[0].model == "fake-model"
    assert logs[0].latency_ms == 5
    assert logs[0].error_type is None


@pytest.mark.asyncio
async def test_timeout_is_logged_as_failure_and_still_raises(db_session: Session) -> None:
    fake = FakeAIProvider()
    fake.queue_timeout()
    user_id = create_user(db_session, email="metering2@example.com").id
    metered = MeteredAIProvider(fake, db=db_session, user_id=user_id, provider_name="groq")

    with pytest.raises(AITimeoutError):
        await metered.chat([])

    logs = _all_logs(db_session)
    assert len(logs) == 1
    assert logs[0].success is False
    assert logs[0].error_type == "AITimeoutError"
    assert logs[0].model is None


@pytest.mark.asyncio
async def test_request_error_is_logged_as_failure(db_session: Session) -> None:
    fake = FakeAIProvider()
    fake.queue_request_error()
    user_id = create_user(db_session, email="metering3@example.com").id
    metered = MeteredAIProvider(fake, db=db_session, user_id=user_id, provider_name="groq")

    with pytest.raises(AIRequestError):
        await metered.transcribe(b"x", filename="a.wav", content_type="audio/wav")

    logs = _all_logs(db_session)
    assert len(logs) == 1
    assert logs[0].operation == AiCallOperation.TRANSCRIBE
    assert logs[0].success is False
    assert logs[0].error_type == "AIRequestError"


@pytest.mark.asyncio
async def test_speech_success_is_logged(db_session: Session) -> None:
    fake = FakeAIProvider()
    fake.queue_speech()
    user_id = create_user(db_session, email="metering4@example.com").id
    metered = MeteredAIProvider(fake, db=db_session, user_id=user_id, provider_name="groq")

    await metered.synthesize_speech("hello", voice="alloy")

    logs = _all_logs(db_session)
    assert len(logs) == 1
    assert logs[0].operation == AiCallOperation.SPEECH
    assert logs[0].success is True
