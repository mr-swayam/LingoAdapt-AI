import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.progress import LessonAttempt, LessonAttemptStatus
from app.repositories import course_repository
from app.services.learner_model_service import record_answer_learning_event
from tests.course_fixtures import build_lesson_with_all_types


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


def test_activity_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me/activity")
    assert response.status_code == 401


def test_activity_shape_for_a_user_with_no_history(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/me/activity", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["lesson_completion"] == {"started": 0, "completed": 0, "completion_rate": 0.0}
    assert body["practice_completion"] == {"started": 0, "completed": 0, "completion_rate": 0.0}
    assert len(body["accuracy_trend"]) == 8
    assert all(p["total"] == 0 for p in body["accuracy_trend"])


def test_activity_reflects_this_users_completed_lesson_only(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_lesson_with_all_types(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    headers_a = _auth_headers(token_a)

    start = client.post(f"/api/v1/lessons/{fixture.lesson_id}/start", headers=headers_a).json()
    attempt = db_session.get(LessonAttempt, uuid.UUID(start["lesson_attempt_id"]))
    assert attempt is not None
    attempt.status = LessonAttemptStatus.COMPLETED
    db_session.commit()

    body_a = client.get("/api/v1/me/activity", headers=headers_a).json()
    assert body_a["lesson_completion"] == {"started": 1, "completed": 1, "completion_rate": 1.0}

    # A second, unrelated user must not see the first user's completion.
    token_b = _signup_and_get_token(client, email="b@example.com")
    body_b = client.get("/api/v1/me/activity", headers=_auth_headers(token_b)).json()
    assert body_b["lesson_completion"] == {"started": 0, "completed": 0, "completion_rate": 0.0}


def test_activity_accuracy_trend_reflects_this_users_learning_events_only(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_lesson_with_all_types(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    token_b = _signup_and_get_token(client, email="b@example.com")

    user_a_id = uuid.UUID(client.get("/api/v1/me", headers=_auth_headers(token_a)).json()["id"])
    user_b_id = uuid.UUID(client.get("/api/v1/me", headers=_auth_headers(token_b)).json()["id"])

    exercise_id = next(iter(fixture.exercise_ids.values()))
    exercise = course_repository.get_exercise(db_session, exercise_id)
    assert exercise is not None

    for _ in range(3):
        record_answer_learning_event(
            db_session, user_id=user_a_id, exercise=exercise, is_correct=True
        )
    record_answer_learning_event(
        db_session, user_id=user_a_id, exercise=exercise, is_correct=False
    )
    record_answer_learning_event(
        db_session, user_id=user_b_id, exercise=exercise, is_correct=True
    )
    db_session.commit()

    body_a = client.get("/api/v1/me/activity", headers=_auth_headers(token_a)).json()
    this_week_a = body_a["accuracy_trend"][-1]
    assert this_week_a["total"] == 4
    assert this_week_a["correct"] == 3
    assert this_week_a["accuracy"] == 0.75

    body_b = client.get("/api/v1/me/activity", headers=_auth_headers(token_b)).json()
    this_week_b = body_b["accuracy_trend"][-1]
    assert this_week_b["total"] == 1
    assert this_week_b["correct"] == 1
