from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


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


def _make_admin(db: Session, email: str) -> None:
    user = db.query(User).filter(User.email == email).one()
    user.is_admin = True
    db.commit()


def _signup_admin(client: TestClient, db: Session, email: str = "admin@example.com") -> str:
    token = _signup_and_get_token(client, email)
    _make_admin(db, email)
    return token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_language(client: TestClient, token: str, code: str = "fr") -> str:
    response = client.post(
        "/api/v1/admin/languages",
        headers=_auth_headers(token),
        json={"code": code, "name": "French"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_course(client: TestClient, token: str, language_id: str) -> dict:
    response = client.post(
        "/api/v1/admin/courses",
        headers=_auth_headers(token),
        json={"language_id": language_id, "title": "French Basics", "description": "d"},
    )
    assert response.status_code == 200
    return response.json()


# --- Access control ---


def test_non_admin_cannot_access_admin_endpoints(client: TestClient, db_session: Session) -> None:
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/admin/courses", headers=_auth_headers(token))
    assert response.status_code == 403


def test_unauthenticated_cannot_access_admin_endpoints(client: TestClient) -> None:
    response = client.get("/api/v1/admin/courses")
    assert response.status_code == 401


# --- Languages ---


def test_admin_can_create_and_list_languages(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)
    _create_language(client, token, code="de")

    response = client.get("/api/v1/admin/languages", headers=_auth_headers(token))
    assert response.status_code == 200
    assert any(lang["code"] == "de" for lang in response.json())


def test_duplicate_language_code_is_rejected(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)
    _create_language(client, token, code="it")
    response = client.post(
        "/api/v1/admin/languages",
        headers=_auth_headers(token),
        json={"code": "it", "name": "Italian Again"},
    )
    assert response.status_code == 409


# --- Courses start as drafts ---


def test_new_course_starts_unpublished_and_hidden_from_learners(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_admin(client, db_session)
    language_id = _create_language(client, token)
    course = _create_course(client, token, language_id)

    assert course["is_published"] is False

    public_courses = client.get("/api/v1/courses").json()
    assert all(c["id"] != course["id"] for c in public_courses)


def test_admin_can_update_course_fields(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)
    language_id = _create_language(client, token)
    course = _create_course(client, token, language_id)

    response = client.patch(
        f"/api/v1/admin/courses/{course['id']}",
        headers=_auth_headers(token),
        json={"title": "Updated Title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


# --- Full authoring + publish workflow ---


def _build_full_course(client: TestClient, token: str) -> dict:
    language_id = _create_language(client, token)
    course = _create_course(client, token, language_id)

    unit = client.post(
        "/api/v1/admin/units",
        headers=_auth_headers(token),
        json={"course_id": course["id"], "title": "Unit 1"},
    ).json()
    lesson = client.post(
        "/api/v1/admin/lessons",
        headers=_auth_headers(token),
        json={"unit_id": unit["id"], "title": "Lesson 1"},
    ).json()
    skill = client.post(
        "/api/v1/admin/skills",
        headers=_auth_headers(token),
        json={"course_id": course["id"], "code": "GREETING", "name": "Greeting"},
    ).json()

    return {"course": course, "unit": unit, "lesson": lesson, "skill": skill}


def test_validate_reports_errors_for_an_empty_course(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_admin(client, db_session)
    language_id = _create_language(client, token)
    course = _create_course(client, token, language_id)

    response = client.get(
        f"/api/v1/admin/courses/{course['id']}/validate", headers=_auth_headers(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any("no units" in e for e in body["errors"])


def test_publish_blocked_until_content_is_valid(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)
    scaffold = _build_full_course(client, token)

    publish_attempt = client.post(
        f"/api/v1/admin/courses/{scaffold['course']['id']}/publish", headers=_auth_headers(token)
    )
    assert publish_attempt.status_code == 422
    assert "errors" in publish_attempt.json()["detail"]

    exercise = client.post(
        "/api/v1/admin/exercises",
        headers=_auth_headers(token),
        json={
            "lesson_id": scaffold["lesson"]["id"],
            "skill_id": scaffold["skill"]["id"],
            "type": "FILL_BLANK",
            "prompt": "Say hello",
            "payload": {"sentence": "___!"},
            "correct_answer": {"answers": ["Hello"]},
            "difficulty": 0.3,
        },
    )
    assert exercise.status_code == 200

    publish = client.post(
        f"/api/v1/admin/courses/{scaffold['course']['id']}/publish", headers=_auth_headers(token)
    )
    assert publish.status_code == 200
    assert publish.json()["is_published"] is True

    public_courses = client.get("/api/v1/courses").json()
    assert any(c["id"] == scaffold["course"]["id"] for c in public_courses)


def test_multiple_choice_exercise_with_options_round_trips(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_admin(client, db_session)
    scaffold = _build_full_course(client, token)

    response = client.post(
        "/api/v1/admin/exercises",
        headers=_auth_headers(token),
        json={
            "lesson_id": scaffold["lesson"]["id"],
            "skill_id": scaffold["skill"]["id"],
            "type": "MULTIPLE_CHOICE",
            "prompt": "Pick the greeting",
            "options": [
                {"text": "Hello", "is_correct": True},
                {"text": "Goodbye", "is_correct": False},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["options"]) == 2
    assert sum(1 for o in body["options"] if o["is_correct"]) == 1


def test_update_exercise_replaces_options(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)
    scaffold = _build_full_course(client, token)
    exercise = client.post(
        "/api/v1/admin/exercises",
        headers=_auth_headers(token),
        json={
            "lesson_id": scaffold["lesson"]["id"],
            "skill_id": scaffold["skill"]["id"],
            "type": "MULTIPLE_CHOICE",
            "prompt": "Pick one",
            "options": [
                {"text": "A", "is_correct": True},
                {"text": "B", "is_correct": False},
            ],
        },
    ).json()

    updated = client.patch(
        f"/api/v1/admin/exercises/{exercise['id']}",
        headers=_auth_headers(token),
        json={"options": [{"text": "C", "is_correct": True}]},
    )
    assert updated.status_code == 200
    assert len(updated.json()["options"]) == 1
    assert updated.json()["options"][0]["text"] == "C"


def test_delete_exercise_lesson_unit_course(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)
    scaffold = _build_full_course(client, token)
    exercise = client.post(
        "/api/v1/admin/exercises",
        headers=_auth_headers(token),
        json={
            "lesson_id": scaffold["lesson"]["id"],
            "skill_id": scaffold["skill"]["id"],
            "type": "FILL_BLANK",
            "prompt": "x",
            "correct_answer": {"answers": ["x"]},
        },
    ).json()

    assert client.delete(
        f"/api/v1/admin/exercises/{exercise['id']}", headers=_auth_headers(token)
    ).status_code == 204
    assert client.delete(
        f"/api/v1/admin/lessons/{scaffold['lesson']['id']}", headers=_auth_headers(token)
    ).status_code == 204
    assert client.delete(
        f"/api/v1/admin/units/{scaffold['unit']['id']}", headers=_auth_headers(token)
    ).status_code == 204
    assert client.delete(
        f"/api/v1/admin/courses/{scaffold['course']['id']}", headers=_auth_headers(token)
    ).status_code == 204

    assert client.get(
        f"/api/v1/admin/courses/{scaffold['course']['id']}", headers=_auth_headers(token)
    ).status_code == 404


def test_duplicate_skill_code_within_a_course_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_admin(client, db_session)
    language_id = _create_language(client, token)
    course = _create_course(client, token, language_id)
    client.post(
        "/api/v1/admin/skills",
        headers=_auth_headers(token),
        json={"course_id": course["id"], "code": "GREETING", "name": "Greeting"},
    )
    response = client.post(
        "/api/v1/admin/skills",
        headers=_auth_headers(token),
        json={"course_id": course["id"], "code": "GREETING", "name": "Again"},
    )
    assert response.status_code == 409


def test_unpublish_hides_a_previously_published_course(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_admin(client, db_session)
    scaffold = _build_full_course(client, token)
    client.post(
        "/api/v1/admin/exercises",
        headers=_auth_headers(token),
        json={
            "lesson_id": scaffold["lesson"]["id"],
            "skill_id": scaffold["skill"]["id"],
            "type": "FILL_BLANK",
            "prompt": "x",
            "correct_answer": {"answers": ["x"]},
        },
    )
    course_id = scaffold["course"]["id"]
    client.post(f"/api/v1/admin/courses/{course_id}/publish", headers=_auth_headers(token))

    unpublish = client.post(
        f"/api/v1/admin/courses/{course_id}/unpublish", headers=_auth_headers(token)
    )
    assert unpublish.status_code == 200
    assert unpublish.json()["is_published"] is False

    public_courses = client.get("/api/v1/courses").json()
    assert all(c["id"] != course_id for c in public_courses)
