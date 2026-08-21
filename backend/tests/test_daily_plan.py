"""V3.2 Personalized Daily Plan: task selection, the completion-stability
fix for the regenerated-every-request problem (architecture review item 1),
the local-day vs UTC-day resolution (item 13), and TaskType staying
restricted to the 3 currently-supported values (item 2).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories import course_repository, learner_model_repository
from app.services.learner_model_service import record_answer_learning_event
from tests.practice_fixtures import build_multi_skill_course


def _signup(client: TestClient, email: str = "learner@example.com") -> tuple[str, uuid.UUID]:
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
    body = response.json()
    return body["access_token"], uuid.UUID(body["user"]["id"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_daily_plan_task_types_are_always_within_the_three_supported_values(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token, user_id = _signup(client)
    exercise = course_repository.get_exercise(db_session, fixture.exercise_ids["SKILL_A"][0])
    assert exercise is not None
    record_answer_learning_event(db_session, user_id=user_id, exercise=exercise, is_correct=False)
    db_session.commit()

    body = client.get("/api/v1/me/daily-plan", headers=_auth_headers(token)).json()

    assert body["tasks"], "expected at least one task for a learner with some history"
    assert {t["task_type"] for t in body["tasks"]} <= {"REVIEW", "PRACTICE", "LESSON"}


def test_daily_plan_includes_a_lesson_task_for_a_fresh_user(
    client: TestClient, db_session: Session
) -> None:
    build_multi_skill_course(db_session)
    token, _ = _signup(client)

    body = client.get("/api/v1/me/daily-plan", headers=_auth_headers(token)).json()

    lesson_tasks = [t for t in body["tasks"] if t["task_type"] == "LESSON"]
    assert len(lesson_tasks) == 1
    assert lesson_tasks[0]["lesson_id"] is not None


def test_review_task_appears_for_a_skill_due_for_review_and_takes_priority_over_practice(
    client: TestClient, db_session: Session
) -> None:
    """A skill that is both weak (would independently rank for PRACTICE)
    and due for review must appear only once, as REVIEW - no duplicate task
    for the same skill."""
    fixture = build_multi_skill_course(db_session)
    token, user_id = _signup(client)
    exercise = course_repository.get_exercise(db_session, fixture.exercise_ids["SKILL_A"][0])
    assert exercise is not None
    record_answer_learning_event(db_session, user_id=user_id, exercise=exercise, is_correct=False)
    db_session.commit()

    mastery_row = learner_model_repository.get_skill_mastery(
        db_session, user_id=user_id, skill_id=fixture.skill_ids["SKILL_A"]
    )
    assert mastery_row is not None
    mastery_row.next_review_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    body = client.get("/api/v1/me/daily-plan", headers=_auth_headers(token)).json()

    skill_a_tasks = [t for t in body["tasks"] if t["skill_name"] == "SKILL_A"]
    assert len(skill_a_tasks) == 1
    assert skill_a_tasks[0]["task_type"] == "REVIEW"


def test_practice_task_completion_is_stable_across_multiple_requests_the_same_day(
    client: TestClient, db_session: Session
) -> None:
    """The exact scenario architecture review item 1 was about: the plan is
    regenerated on every GET, so completion must be based on a stable, live
    condition (SkillMastery.last_practiced_at vs. the start of today), not
    a per-request timestamp that would make a done task look undone again
    on the very next call."""
    fixture = build_multi_skill_course(db_session)
    token, user_id = _signup(client)
    exercise = course_repository.get_exercise(db_session, fixture.exercise_ids["SKILL_A"][0])
    assert exercise is not None
    record_answer_learning_event(db_session, user_id=user_id, exercise=exercise, is_correct=False)
    db_session.commit()
    # Seeding a mastery row is itself "practicing" (sets last_practiced_at =
    # now) - backdate it to yesterday so the task starts genuinely not-done
    # for today, and today's real practice below is what flips it.
    mastery_row = learner_model_repository.get_skill_mastery(
        db_session, user_id=user_id, skill_id=fixture.skill_ids["SKILL_A"]
    )
    assert mastery_row is not None
    mastery_row.last_practiced_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    before = client.get("/api/v1/me/daily-plan", headers=_auth_headers(token)).json()
    task_before = next(t for t in before["tasks"] if t["skill_name"] == "SKILL_A")
    assert task_before["completed"] is False

    # Practice the skill for real via the general adaptive session.
    start = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    exercise_in_session = next(
        ex for ex in start["exercises"] if ex["id"] == str(fixture.exercise_ids["SKILL_A"][0])
    )
    correct_option_id = str(
        fixture.options[uuid.UUID(exercise_in_session["id"])].correct
    )
    client.post(
        f"/api/v1/practice/{start['practice_session_id']}/answer",
        headers=_auth_headers(token),
        json={
            "exercise_id": exercise_in_session["id"],
            "submitted_answer": {"option_id": correct_option_id},
        },
    )

    first_after = client.get("/api/v1/me/daily-plan", headers=_auth_headers(token)).json()
    second_after = client.get("/api/v1/me/daily-plan", headers=_auth_headers(token)).json()

    task_first_after = next(t for t in first_after["tasks"] if t["skill_name"] == "SKILL_A")
    task_second_after = next(t for t in second_after["tasks"] if t["skill_name"] == "SKILL_A")
    assert task_first_after["completed"] is True
    assert task_second_after["completed"] is True  # still true - not a per-request fluke


def test_local_date_changes_practice_completion_state_for_the_same_timestamp(
    client: TestClient, db_session: Session
) -> None:
    """Architecture review item 13: no per-user timezone is stored anywhere,
    so `local_date` is the sole determinant of "today" for the practice
    completion boundary. The same last_practiced_at must read as completed
    for a local_date that still contains it, and not-completed for a
    local_date whose day has already moved past it."""
    fixture = build_multi_skill_course(db_session)
    token, user_id = _signup(client)
    exercise = course_repository.get_exercise(db_session, fixture.exercise_ids["SKILL_A"][0])
    assert exercise is not None
    record_answer_learning_event(db_session, user_id=user_id, exercise=exercise, is_correct=True)
    db_session.commit()

    mastery_row = learner_model_repository.get_skill_mastery(
        db_session, user_id=user_id, skill_id=fixture.skill_ids["SKILL_A"]
    )
    assert mastery_row is not None
    mastery_row.last_practiced_at = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)
    db_session.commit()

    same_day = client.get(
        "/api/v1/me/daily-plan", headers=_auth_headers(token), params={"local_date": "2026-01-01"}
    ).json()
    next_day = client.get(
        "/api/v1/me/daily-plan", headers=_auth_headers(token), params={"local_date": "2026-01-02"}
    ).json()

    same_day_task = next(t for t in same_day["tasks"] if t["skill_name"] == "SKILL_A")
    next_day_task = next(t for t in next_day["tasks"] if t["skill_name"] == "SKILL_A")
    assert same_day_task["completed"] is True
    assert next_day_task["completed"] is False
    assert same_day["generated_for_date"] == "2026-01-01"
    assert next_day["generated_for_date"] == "2026-01-02"


def test_local_date_is_optional_and_falls_back_to_utc_today(
    client: TestClient, db_session: Session
) -> None:
    build_multi_skill_course(db_session)
    token, _ = _signup(client)

    response = client.get("/api/v1/me/daily-plan", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["generated_for_date"] == datetime.now(UTC).date().isoformat()


def test_daily_plan_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me/daily-plan")
    assert response.status_code == 401
