import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.progress import LessonAttempt, LessonAttemptStatus
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


def test_list_courses_includes_seeded_course(client: TestClient, db_session: Session) -> None:
    build_lesson_with_all_types(db_session)

    response = client.get("/api/v1/courses")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Test Course"
    assert body[0]["language_code"] == "en"
    assert body[0]["unit_count"] == 1
    assert body[0]["lesson_count"] == 1


def test_get_course_detail_includes_units_and_lessons(
    client: TestClient, db_session: Session
) -> None:
    build_lesson_with_all_types(db_session)
    course_id = client.get("/api/v1/courses").json()[0]["id"]
    token = _signup_and_get_token(client)

    response = client.get(f"/api/v1/courses/{course_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["units"]) == 1
    assert body["units"][0]["lessons"][0]["title"] == "Lesson 1"
    assert body["units"][0]["lessons"][0]["exercise_count"] == 5
    assert body["units"][0]["lessons"][0]["completed"] is False


def test_get_course_detail_marks_completed_lessons_for_the_current_user(
    client: TestClient, db_session: Session
) -> None:
    build_lesson_with_all_types(db_session)
    course_id = client.get("/api/v1/courses").json()[0]["id"]
    token = _signup_and_get_token(client)
    headers = _auth_headers(token)

    lesson_id = client.get(f"/api/v1/courses/{course_id}", headers=headers).json()["units"][0][
        "lessons"
    ][0]["id"]
    start = client.post(f"/api/v1/lessons/{lesson_id}/start", headers=headers).json()

    # Directly mark the attempt completed rather than answering all 5
    # exercise types correctly through the API - this test is about
    # /courses/{id}'s "completed" field reflecting real attempt state, not
    # about re-testing lesson-completion grading (covered elsewhere).
    attempt = db_session.get(LessonAttempt, uuid.UUID(start["lesson_attempt_id"]))
    assert attempt is not None
    attempt.status = LessonAttemptStatus.COMPLETED
    db_session.commit()

    response = client.get(f"/api/v1/courses/{course_id}", headers=headers)
    assert response.json()["units"][0]["lessons"][0]["completed"] is True

    # A different learner who hasn't touched this lesson must not see it as completed.
    other_token = _signup_and_get_token(client, email="other@example.com")
    other_response = client.get(f"/api/v1/courses/{course_id}", headers=_auth_headers(other_token))
    assert other_response.json()["units"][0]["lessons"][0]["completed"] is False


def test_get_course_detail_requires_authentication(client: TestClient, db_session: Session) -> None:
    build_lesson_with_all_types(db_session)
    course_id = client.get("/api/v1/courses").json()[0]["id"]

    response = client.get(f"/api/v1/courses/{course_id}")
    assert response.status_code == 401


def test_get_course_detail_404_for_unknown_id(client: TestClient) -> None:
    token = _signup_and_get_token(client)
    response = client.get(
        "/api/v1/courses/00000000-0000-0000-0000-000000000000", headers=_auth_headers(token)
    )
    assert response.status_code == 404
