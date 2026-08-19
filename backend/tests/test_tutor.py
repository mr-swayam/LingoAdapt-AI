import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.main import app
from app.models.conversation import ConversationMessage
from app.models.evaluation import DetectedError
from app.models.learner_model import LearningEvent, LearningEventType
from tests.ai_fixtures import FakeAIProvider
from tests.conversation_fixtures import build_grammar_skills


def _signup_and_get_token(client: TestClient, email: str = "learner@example.com") -> str:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "native_language": "en",
            "target_language": "es",
            "daily_goal_xp": 50,
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _start_conversation(client: TestClient, token: str, scenario: str = "RESTAURANT") -> dict:
    response = client.post(
        "/api/v1/tutor/conversations",
        headers=_auth_headers(token),
        json={"scenario": scenario},
    )
    assert response.status_code == 200
    return response.json()


def test_start_conversation_creates_active_conversation(client: TestClient) -> None:
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token, scenario="AIRPORT")

    assert conversation["scenario"] == "AIRPORT"
    assert conversation["status"] == "ACTIVE"
    assert conversation["summary"] is None
    assert conversation["ended_at"] is None


def test_send_message_returns_reply_with_no_corrections(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_conversation_turn(reply="Welcome! What would you like to order?")
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Hello, table for one please."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["learner_message"]["content"] == "Hello, table for one please."
    assert body["learner_message"]["role"] == "LEARNER"
    assert body["tutor_message"]["content"] == "Welcome! What would you like to order?"
    assert body["tutor_message"]["role"] == "TUTOR"
    assert body["corrections"] == []


def test_send_message_with_correction_records_learning_event_and_mastery(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_conversation_turn(
        reply="Nice! Where did you go?",
        corrections=[
            {
                "original": "I go there yesterday",
                "corrected": "I went there yesterday",
                "explanation": "Use past tense for completed actions.",
                "skill": "past tense",
            }
        ],
    )
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "I go there yesterday"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["corrections"]) == 1
    assert body["corrections"][0]["skill"] == "PAST_TENSE"
    assert body["corrections"][0]["corrected"] == "I went there yesterday"

    events = db_session.execute(select(LearningEvent)).scalars().all()
    assert len(events) == 1
    assert events[0].event_type == LearningEventType.CONVERSATION_CORRECTION
    assert events[0].is_correct is False
    assert events[0].exercise_id is None
    assert events[0].conversation_message_id is not None

    errors = db_session.execute(select(DetectedError)).scalars().all()
    assert len(errors) == 1
    assert errors[0].error_type == "GRAMMAR"
    assert errors[0].submitted_text == "I go there yesterday"

    mastery = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    assert len(mastery) == 1
    assert mastery[0]["mastery"] < 50.0  # incorrect answer pulls mastery down from 0 baseline


def test_conversation_history_preserves_message_order(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    fake_ai_provider.queue_conversation_turn(reply="Hi there!")
    client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Hello"},
    )
    fake_ai_provider.queue_conversation_turn(reply="I'm doing well, thanks!")
    client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "How are you?"},
    )

    detail = client.get(
        f"/api/v1/tutor/conversations/{conversation['id']}", headers=_auth_headers(token)
    ).json()

    contents = [m["content"] for m in detail["messages"]]
    assert contents == ["Hello", "Hi there!", "How are you?", "I'm doing well, thanks!"]

    # Second call's prompt included the first turn as history context.
    assert len(fake_ai_provider.calls) == 2
    second_call_messages = fake_ai_provider.calls[1]
    joined = " ".join(m.content for m in second_call_messages)
    assert "Hello" in joined and "Hi there!" in joined


def test_list_conversations_returns_users_own_conversations(client: TestClient) -> None:
    token = _signup_and_get_token(client)
    _start_conversation(client, token, scenario="RESTAURANT")
    _start_conversation(client, token, scenario="AIRPORT")

    conversations = client.get(
        "/api/v1/tutor/conversations", headers=_auth_headers(token)
    ).json()

    assert len(conversations) == 2
    assert {c["scenario"] for c in conversations} == {"RESTAURANT", "AIRPORT"}


def test_cannot_access_another_users_conversation(client: TestClient) -> None:
    token_a = _signup_and_get_token(client, email="a@example.com")
    conversation = _start_conversation(client, token_a)

    token_b = _signup_and_get_token(client, email="b@example.com")
    response = client.get(
        f"/api/v1/tutor/conversations/{conversation['id']}", headers=_auth_headers(token_b)
    )
    assert response.status_code == 403


def test_nonexistent_conversation_returns_404(client: TestClient) -> None:
    token = _signup_and_get_token(client)
    response = client.get(
        f"/api/v1/tutor/conversations/{uuid.uuid4()}", headers=_auth_headers(token)
    )
    assert response.status_code == 404


def test_end_conversation_sets_deterministic_summary(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token, scenario="AIRPORT")

    fake_ai_provider.queue_conversation_turn(reply="Which gate are you looking for?")
    client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Where is gate 12?"},
    )

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/end", headers=_auth_headers(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ENDED"
    assert body["ended_at"] is not None
    assert body["summary"] is not None
    assert "Airport" in body["summary"]

    # AI is never called to produce a summary - fake provider was only
    # invoked once, for the single message turn above.
    assert len(fake_ai_provider.calls) == 1


def test_sending_message_to_ended_conversation_returns_409(
    client: TestClient, db_session: Session
) -> None:
    build_grammar_skills(db_session)
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/end", headers=_auth_headers(token)
    )

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Still there?"},
    )
    assert response.status_code == 409


def test_ai_timeout_does_not_corrupt_conversation_state(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_timeout()
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Hello"},
    )

    assert response.status_code == 503
    assert db_session.execute(select(ConversationMessage)).scalars().first() is None


def test_ai_provider_not_configured_returns_503(client: TestClient, db_session: Session) -> None:
    build_grammar_skills(db_session)
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    app.dependency_overrides[get_ai_provider] = lambda: None
    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Hello"},
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_malformed_ai_response_returns_503_and_records_nothing(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_raw_content("not json")
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Hello"},
    )

    assert response.status_code == 503
    assert db_session.execute(select(ConversationMessage)).scalars().first() is None
