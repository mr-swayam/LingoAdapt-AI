import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.main import app
from app.models.learner_model import LearningEvent
from app.models.progress import ExerciseAttempt
from app.repositories import course_repository
from app.services.learner_model_service import record_answer_learning_event
from tests.ai_fixtures import FakeAIProvider
from tests.speaking_listening_fixtures import build_speaking_listening_lesson


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


def test_speaking_exercise_payload_shows_phrase_but_not_accepted_answers(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)

    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    speaking = next(ex for ex in start["exercises"] if ex["type"] == "SPEAKING")
    assert speaking["payload"]["phrase_to_say"] == "Can I have the bill, please?"


def test_listening_exercise_hides_text_to_speak(client: TestClient, db_session: Session) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)

    raw = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).text
    assert "glass of water" not in raw  # the dictation answer must never reach the client


def test_correct_speaking_answer_updates_mastery(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    fake_ai_provider.queue_transcription("Can I have the bill, please?")
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/answer-audio",
        headers=_auth_headers(token),
        data={"lesson_attempt_id": start["lesson_attempt_id"]},
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["transcript"] == "Can I have the bill, please?"
    assert "matched" in body["correct_answer"]["feedback"]

    mastery = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    assert mastery[0]["mastery"] == 8.0  # same EMA formula as every other exercise type


def test_mispronounced_speaking_answer_is_incorrect_with_feedback(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    fake_ai_provider.queue_transcription("Can I have the bell please")
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/answer-audio",
        headers=_auth_headers(token),
        data={"lesson_attempt_id": start["lesson_attempt_id"]},
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    assert "bill" in body["correct_answer"]["feedback"]
    assert "bell" in body["correct_answer"]["feedback"]


def test_resubmitting_a_speaking_answer_does_not_call_ai_again(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    fake_ai_provider.queue_transcription("Can I have the bill, please?")
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    data = {"lesson_attempt_id": start["lesson_attempt_id"]}
    files = {"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")}

    first = client.post(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/answer-audio",
        headers=_auth_headers(token),
        data=data,
        files=files,
    )
    assert first.status_code == 200
    assert len(fake_ai_provider.transcribe_calls) == 1

    # The lesson has a second (LISTENING) exercise, so the attempt is still
    # IN_PROGRESS - resubmitting the SAME exercise mid-attempt must hit the
    # idempotency pre-check and skip transcription entirely, not just skip
    # re-grading.
    second = client.post(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/answer-audio",
        headers=_auth_headers(token),
        data=data,
        files=files,
    )
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(fake_ai_provider.transcribe_calls) == 1  # unchanged - no second AI call


def test_speaking_works_in_practice_sessions_too(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)

    me = client.get("/api/v1/me", headers=_auth_headers(token)).json()
    user_id = uuid.UUID(me["id"])
    exercise = course_repository.get_exercise(db_session, fixture.speaking_exercise_id)
    assert exercise is not None
    record_answer_learning_event(db_session, user_id=user_id, exercise=exercise, is_correct=False)
    db_session.commit()

    fake_ai_provider.queue_transcription("Can I have the bill, please?")
    start = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    assert start["total_count"] >= 1

    speaking_id = str(fixture.speaking_exercise_id)
    response = client.post(
        f"/api/v1/practice/{start['practice_session_id']}/answer-audio",
        headers=_auth_headers(token),
        data={"exercise_id": speaking_id},
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["is_correct"] is True
    assert response.json()["transcript"] == "Can I have the bill, please?"


def test_ai_timeout_during_speaking_answer_does_not_corrupt_state(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    fake_ai_provider.queue_timeout()
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/answer-audio",
        headers=_auth_headers(token),
        data={"lesson_attempt_id": start["lesson_attempt_id"]},
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 503
    assert db_session.execute(select(ExerciseAttempt)).scalars().first() is None
    assert db_session.execute(select(LearningEvent)).scalars().first() is None


def test_ai_provider_not_configured_returns_503_for_speaking(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    app.dependency_overrides[get_ai_provider] = lambda: None
    response = client.post(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/answer-audio",
        headers=_auth_headers(token),
        data={"lesson_attempt_id": start["lesson_attempt_id"]},
        files={"file": ("speech.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert response.status_code == 503


def test_oversized_audio_upload_returns_413(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    fake_ai_provider.queue_transcription("Can I have the bill, please?")
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    oversized = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/answer-audio",
        headers=_auth_headers(token),
        data={"lesson_attempt_id": start["lesson_attempt_id"]},
        files={"file": ("speech.webm", oversized, "audio/webm")},
    )
    assert response.status_code == 413
    assert len(fake_ai_provider.transcribe_calls) == 0  # rejected before ever reaching the AI


def test_listening_audio_endpoint_returns_synthesized_audio_and_is_cached(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    fake_ai_provider.queue_speech(audio_bytes=b"RIFF-fake-wav-data", content_type="audio/wav")
    token = _signup_and_get_token(client)

    first = client.get(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/audio", headers=_auth_headers(token)
    )
    assert first.status_code == 200
    assert first.headers["content-type"] == "audio/wav"
    assert first.content == b"RIFF-fake-wav-data"

    second = client.get(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/audio", headers=_auth_headers(token)
    )
    assert second.status_code == 200
    assert second.content == b"RIFF-fake-wav-data"

    assert len(fake_ai_provider.synthesize_calls) == 1  # second fetch served from cache


def test_listening_audio_endpoint_404s_for_non_listening_exercise(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)

    response = client.get(
        f"/api/v1/exercises/{fixture.speaking_exercise_id}/audio", headers=_auth_headers(token)
    )
    assert response.status_code == 404


def test_correct_listening_dictation_via_json_answer_endpoint(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "I would like a glass of water, please."},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["correct_answer"]["category"] == "EXACT"


def test_listening_answer_with_normalization_only_difference_is_correct(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "i would like a glass of water please"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["correct_answer"]["category"] == "NORMALIZED"


def test_listening_answer_with_minor_typo_is_still_correct_with_word_feedback(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "I would like a glas of water, please."},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["correct_answer"]["category"] == "MINOR_ERROR"
    assert "glass" in body["correct_answer"]["words_missing"]
    assert "glas" in body["correct_answer"]["words_incorrect"]


def test_listening_partial_answer_is_incorrect_with_category(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "I would like a glass"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    assert body["correct_answer"]["category"] == "PARTIAL"
    assert "water" in body["correct_answer"]["words_missing"]


def test_listening_major_error_answer_is_incorrect(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "yesterday I go to school"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    assert body["correct_answer"]["category"] == "MAJOR_ERROR"


def test_listening_empty_answer_is_incorrect(client: TestClient, db_session: Session) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": ""},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    assert body["correct_answer"]["category"] == "INCORRECT"


def test_correct_listening_answer_updates_mastery(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_speaking_listening_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.listening_exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "I would like a glass of water, please."},
        },
    )
    assert response.status_code == 200

    mastery = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    assert mastery[0]["mastery"] == 8.0  # same EMA formula as every other exercise type
