import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.main import app
from app.models.evaluation import DetectedError
from app.models.learner_model import LearningEvent
from app.models.progress import ExerciseAttempt
from app.repositories import course_repository
from app.services.learner_model_service import record_answer_learning_event
from tests.ai_fixtures import FakeAIProvider
from tests.short_answer_fixtures import build_short_answer_lesson


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


def test_short_answer_exercise_does_not_leak_model_answer(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_short_answer_lesson(db_session)
    token = _signup_and_get_token(client)

    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    assert start["exercises"][0]["type"] == "SHORT_ANSWER"
    raw = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).text
    assert "Anna" not in raw  # the model_answer/rubric must never reach the client


def test_correct_short_answer_updates_mastery_and_records_no_errors(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_evaluation(is_correct=True, score=0.9, explanation="Nicely done.")
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "My name is Ridhvan."},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["explanation"] == "Nicely done."
    assert body["lesson_completed"] is True

    mastery = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    assert mastery[0]["mastery"] == 8.0  # same formula as deterministic types

    errors = db_session.execute(select(DetectedError)).scalars().all()
    assert errors == []


def test_incorrect_short_answer_records_detected_errors(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_evaluation(
        is_correct=False,
        score=0.2,
        explanation="Missing a verb.",
        corrected_answer="My name is Bob and I am a student.",
        errors=[{"type": "grammar", "skill": "missing verb 'am'", "severity": "major"}],
    )
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "My name Bob and I student."},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    assert body["correct_answer"]["corrected_answer"] == "My name is Bob and I am a student."

    errors_endpoint = client.get("/api/v1/me/errors", headers=_auth_headers(token)).json()
    assert len(errors_endpoint) == 1
    assert errors_endpoint[0]["error_type"] == "GRAMMAR"
    assert errors_endpoint[0]["severity"] == "HIGH"
    assert errors_endpoint[0]["description"] == "missing verb 'am'"


def test_is_correct_true_but_low_score_is_treated_as_incorrect(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    """rules.md: never trust AI output without validation - a numeric floor
    guards against is_correct=true paired with a contradictory low score."""
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_evaluation(is_correct=True, score=0.1)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "..."},
        },
    )

    assert response.json()["is_correct"] is False


def test_resubmitting_a_short_answer_does_not_call_ai_again(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_evaluation(is_correct=True, score=0.9)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    payload = {
        "lesson_attempt_id": start["lesson_attempt_id"],
        "submitted_answer": {"text": "My name is Ridhvan."},
    }

    first = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json=payload,
    )
    assert first.status_code == 200
    assert len(fake_ai_provider.calls) == 1

    # Second submission of the SAME exercise within the same (now-completed)
    # attempt should 409 before ever reaching AI grading again.
    second = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json=payload,
    )
    assert second.status_code == 409
    assert len(fake_ai_provider.calls) == 1  # unchanged - no second AI call


def test_ai_timeout_does_not_corrupt_learning_state(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_timeout()
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "My name is Ridhvan."},
        },
    )

    assert response.status_code == 503

    # Nothing was written: no exercise attempt, no learning event, and the
    # lesson attempt is still IN_PROGRESS (retryable).
    assert db_session.execute(select(ExerciseAttempt)).scalars().first() is None
    assert db_session.execute(select(LearningEvent)).scalars().first() is None

    mastery = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    assert mastery == []


def test_ai_provider_not_configured_returns_503(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_short_answer_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    # The `client` fixture's dependency_overrides dict is reset after every
    # test (see conftest.py), so overriding it here for this test only is safe.
    app.dependency_overrides[get_ai_provider] = lambda: None
    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "My name is Ridhvan."},
        },
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_malformed_ai_response_returns_503_and_records_nothing(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_raw_content("this is not json")
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "My name is Ridhvan."},
        },
    )

    assert response.status_code == 503
    assert db_session.execute(select(ExerciseAttempt)).scalars().first() is None


@pytest.mark.parametrize(
    "ai_error_type,expected_detected_error_type",
    [
        ("grammar", "GRAMMAR"),
        ("spelling", "SPELLING"),
        ("vocabulary", "VOCABULARY"),
        ("word order", "WORD_ORDER"),
        ("something the model invented", "OTHER"),
    ],
)
def test_each_ai_error_category_is_classified_and_persisted(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: FakeAIProvider,
    ai_error_type: str,
    expected_detected_error_type: str,
) -> None:
    """Phase 13 Task 5: deterministic coverage of every error category the
    AI evaluation pipeline can classify, mirroring the AI evaluation
    quality audit's category list (grammar/spelling/vocabulary/word-order)."""
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_evaluation(
        is_correct=False,
        score=0.2,
        explanation="Needs work.",
        corrected_answer="corrected",
        errors=[{"type": ai_error_type, "skill": "example issue", "severity": "medium"}],
    )
    token = _signup_and_get_token(client, email=f"cat-{expected_detected_error_type}@example.com")
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "some answer"},
        },
    )

    assert response.status_code == 200
    errors = db_session.execute(select(DetectedError)).scalars().all()
    assert len(errors) == 1
    assert errors[0].error_type.value == expected_detected_error_type


def test_overly_long_short_answer_is_rejected_before_calling_ai(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    """Phase 12 AI cost control: an oversized answer must never reach the
    paid AI call at all."""
    fixture = build_short_answer_lesson(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    response = client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "x" * 2001},
        },
    )

    assert response.status_code == 400
    assert "too long" in response.json()["detail"]
    assert fake_ai_provider.calls == []


def test_short_answer_works_in_practice_sessions_too(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_short_answer_lesson(db_session)
    token = _signup_and_get_token(client)

    # Build history the same way the lesson flow would, via a direct
    # learning event, so the skill is a practice candidate.
    me = client.get("/api/v1/me", headers=_auth_headers(token)).json()
    user_id = uuid.UUID(me["id"])
    exercise = course_repository.get_exercise(db_session, fixture.exercise_id)
    assert exercise is not None
    record_answer_learning_event(db_session, user_id=user_id, exercise=exercise, is_correct=True)
    db_session.commit()

    fake_ai_provider.queue_evaluation(is_correct=True, score=0.9)
    start = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    assert start["total_count"] == 1
    assert start["exercises"][0]["type"] == "SHORT_ANSWER"

    response = client.post(
        f"/api/v1/practice/{start['practice_session_id']}/answer",
        headers=_auth_headers(token),
        json={
            "exercise_id": str(fixture.exercise_id),
            "submitted_answer": {"text": "Hi, I'm Sam."},
        },
    )
    assert response.status_code == 200
    assert response.json()["session_completed"] is True
