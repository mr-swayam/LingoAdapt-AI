from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.course_fixtures import build_lesson_with_all_types


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

    response = client.get(f"/api/v1/courses/{course_id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["units"]) == 1
    assert body["units"][0]["lessons"][0]["title"] == "Lesson 1"
    assert body["units"][0]["lessons"][0]["exercise_count"] == 5


def test_get_course_detail_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/api/v1/courses/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
