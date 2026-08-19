import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import ConversationMessage
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


def test_voice_message_transcribes_and_returns_reply(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_transcription("Hello, table for one please.")
    fake_ai_provider.queue_conversation_turn(reply="Welcome! Right this way.")
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/voice-messages",
        headers=_auth_headers(token),
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "Hello, table for one please."
    assert body["learner_message"]["content"] == "Hello, table for one please."
    assert body["tutor_message"]["content"] == "Welcome! Right this way."
    assert body["corrections"] == []


def test_silent_recording_returns_400_without_creating_messages(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_transcription("")  # silence / inaudible
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/voice-messages",
        headers=_auth_headers(token),
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 400
    assert db_session.execute(select(ConversationMessage)).scalars().first() is None


def test_voice_message_ai_timeout_leaves_no_trace(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_timeout()
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/voice-messages",
        headers=_auth_headers(token),
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 503
    assert db_session.execute(select(ConversationMessage)).scalars().first() is None


def test_voice_message_oversized_audio_returns_413(
    client: TestClient, db_session: Session
) -> None:
    build_grammar_skills(db_session)
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    oversized = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/voice-messages",
        headers=_auth_headers(token),
        files={"file": ("speech.webm", oversized, "audio/webm")},
    )
    assert response.status_code == 413


def test_message_audio_endpoint_returns_synthesized_audio_and_is_cached(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_conversation_turn(reply="Welcome! Right this way.")
    fake_ai_provider.queue_speech(audio_bytes=b"RIFF-tutor-reply", content_type="audio/wav")
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    sent = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Hello"},
    ).json()
    tutor_message_id = sent["tutor_message"]["id"]

    first = client.get(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages/{tutor_message_id}/audio",
        headers=_auth_headers(token),
    )
    assert first.status_code == 200
    assert first.content == b"RIFF-tutor-reply"

    second = client.get(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages/{tutor_message_id}/audio",
        headers=_auth_headers(token),
    )
    assert second.status_code == 200

    assert len(fake_ai_provider.synthesize_calls) == 1  # second fetch served from cache


def test_message_audio_endpoint_404s_for_learner_message(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_conversation_turn(reply="Welcome!")
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    sent = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "Hello"},
    ).json()
    learner_message_id = sent["learner_message"]["id"]

    response = client.get(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages/{learner_message_id}/audio",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_message_audio_endpoint_404s_for_nonexistent_message(
    client: TestClient, db_session: Session
) -> None:
    build_grammar_skills(db_session)
    token = _signup_and_get_token(client)
    conversation = _start_conversation(client, token)

    response = client.get(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages/{uuid.uuid4()}/audio",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_cannot_send_voice_message_to_another_users_conversation(
    client: TestClient, db_session: Session
) -> None:
    build_grammar_skills(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    conversation = _start_conversation(client, token_a)

    token_b = _signup_and_get_token(client, email="b@example.com")
    response = client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/voice-messages",
        headers=_auth_headers(token_b),
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert response.status_code == 403
