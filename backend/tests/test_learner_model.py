import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import ExerciseType
from app.models.learner_model import LearningEvent, SkillMastery
from app.repositories import course_repository
from app.services.learner_model_service import record_answer_learning_event
from tests.course_fixtures import SeededLesson, build_lesson_with_all_types


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


def _answer_multiple_choice(
    client: TestClient, token: str, seeded: SeededLesson, attempt_id: str, *, correct: bool
) -> dict:
    key = "correct" if correct else "wrong"
    exercise_id = seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]
    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": attempt_id,
            "submitted_answer": {
                "option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE][key])
            },
        },
    )
    return response.json()


def test_answering_an_exercise_creates_a_learning_event(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    _answer_multiple_choice(client, token, seeded, attempt_id, correct=True)

    events = db_session.execute(select(LearningEvent)).scalars().all()
    assert len(events) == 1
    assert events[0].is_correct is True
    assert events[0].event_type.value == "ANSWER_SUBMITTED"


def test_mastery_matches_documented_formula_after_one_correct_answer(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    _answer_multiple_choice(client, token, seeded, attempt_id, correct=True)

    response = client.get("/api/v1/me/mastery", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    # Starts at 0, one correct answer -> 0*0.92 + 100*0.08 = 8.0
    assert body[0]["mastery"] == 8.0
    assert body[0]["attempt_count"] == 1
    assert body[0]["correct_count"] == 1
    assert body[0]["confidence"] == 10.0  # 1/10 attempts
    assert body[0]["level"] == "weak"


def test_mastery_accumulates_across_multiple_exercises_of_the_same_skill(
    client: TestClient, db_session: Session
) -> None:
    """All 5 seeded exercise types share one skill (see course_fixtures), so
    answering several should accumulate onto the same skill_mastery row."""
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    client.post(
        f"/api/v1/exercises/{seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": attempt_id,
            "submitted_answer": {
                "option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])
            },
        },
    )
    client.post(
        f"/api/v1/exercises/{seeded.exercise_ids[ExerciseType.FILL_BLANK]}/answer",
        headers=_auth_headers(token),
        json={"lesson_attempt_id": attempt_id, "submitted_answer": {"text": "Hello"}},
    )

    body = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()

    assert len(body) == 1  # still one skill, two attempts against it
    assert body[0]["attempt_count"] == 2
    assert body[0]["correct_count"] == 2


def test_resubmitting_an_answered_exercise_does_not_double_count(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    _answer_multiple_choice(client, token, seeded, attempt_id, correct=True)
    _answer_multiple_choice(client, token, seeded, attempt_id, correct=True)  # idempotent retry

    events = db_session.execute(select(LearningEvent)).scalars().all()
    assert len(events) == 1

    body = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    assert body[0]["attempt_count"] == 1


def test_mastery_level_thresholds(client: TestClient, db_session: Session) -> None:
    """Driving this through the HTTP lesson-attempt flow would need ~20 full
    lesson completions to accumulate enough correct answers on one skill
    (each attempt only permits one fresh answer per exercise, and a resumed
    attempt hits the idempotent no-op path on re-answer). The mastery
    threshold logic itself doesn't care how the events arrived, so drive the
    learner-model service directly to build up state efficiently.
    """
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    exercise = course_repository.get_exercise(
        db_session, seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]
    )
    assert exercise is not None

    me = client.get("/api/v1/me", headers=_auth_headers(token)).json()
    user_id = uuid.UUID(me["id"])

    for _ in range(20):
        record_answer_learning_event(
            db_session, user_id=user_id, exercise=exercise, is_correct=True
        )
    db_session.commit()

    mastery_body = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    assert mastery_body[0]["mastery"] >= 70
    assert mastery_body[0]["level"] == "strong"


def test_mastery_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me/mastery")
    assert response.status_code == 401


def test_review_queue_only_returns_skills_due_now(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]
    _answer_multiple_choice(client, token, seeded, attempt_id, correct=True)

    # The real answer just set next_review_at a day or more in the future -
    # nothing should be due yet.
    not_due = client.get("/api/v1/me/review", headers=_auth_headers(token)).json()
    assert not_due == []

    # Directly backdate the row to simulate time passing, then confirm it
    # shows up as due.
    row = db_session.execute(select(SkillMastery)).scalars().one()
    row.next_review_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    due = client.get("/api/v1/me/review", headers=_auth_headers(token)).json()
    assert len(due) == 1
    assert due[0]["skill_code"] == "TEST_SKILL"


def test_review_queue_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me/review")
    assert response.status_code == 401
