"""Phase 13 Task 6: explicit coverage of failure scenarios not already
exercised elsewhere in the suite - database failure mid-write, and
excessive input (oversized audio upload). The other categories the task
lists (AI timeout, AI provider error, malformed AI response, Redis
unavailable, AI rate limit, unauthorized access) already have dedicated
tests elsewhere - see RELEASE_CANDIDATE_REPORT.md for the full inventory
mapping each scenario to its covering test(s).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.main import app
from app.models.learner_model import LearningEvent
from app.models.progress import ExerciseAttempt
from app.repositories import progress_repository
from tests.course_fixtures import build_lesson_with_all_types


def _signup(client: TestClient, email: str) -> str:
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "native_language": "en",
            "target_language": "es",
            "daily_goal_xp": 50,
        },
    )
    assert r.status_code == 201
    return r.json()["access_token"]


def test_database_failure_mid_answer_leaves_no_partial_state(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DB error while recording an answer must not corrupt state - no
    partial ExerciseAttempt/LearningEvent row, and the client gets a clean
    (non-leaking) error rather than a raw traceback."""
    fixture = build_lesson_with_all_types(db_session)
    token = _signup(client, "dbfail@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=headers
    ).json()
    first_type = next(iter(fixture.exercise_ids))
    exercise_id = fixture.exercise_ids[first_type]
    correct_option_id = str(fixture.option_ids[first_type]["correct"])

    def _boom(*args: object, **kwargs: object) -> None:
        raise OperationalError("INSERT ...", {}, Exception("connection lost"))

    monkeypatch.setattr(progress_repository, "record_exercise_attempt", _boom)

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    # Reuse the same overridden dependencies the `client` fixture already set up.
    response = no_raise_client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=headers,
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"option_id": correct_option_id},
        },
    )

    assert response.status_code == 500
    assert "request_id" in response.json()

    assert db_session.execute(select(ExerciseAttempt)).scalars().first() is None
    assert db_session.execute(select(LearningEvent)).scalars().first() is None


def test_oversized_audio_upload_is_rejected(client: TestClient, db_session: Session) -> None:
    from app.services.speech_service import MAX_AUDIO_BYTES

    fixture = build_lesson_with_all_types(db_session)
    token = _signup(client, "bigaudio@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=headers
    ).json()

    # SPEAKING isn't in this fixture's exercise set; the audio-size guard
    # runs before any type-specific logic, at the API boundary, so hitting
    # it with any exercise id proves the size check itself works without
    # needing a real SPEAKING exercise fixture.
    exercise_id = fixture.exercise_ids[list(fixture.exercise_ids.keys())[0]]
    oversized_audio = b"x" * (MAX_AUDIO_BYTES + 1)

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer-audio",
        headers=headers,
        data={"lesson_attempt_id": start["lesson_attempt_id"]},
        files={"file": ("big.wav", oversized_audio, "audio/wav")},
    )

    assert response.status_code == 413
    assert "large" in response.json()["detail"].lower()
