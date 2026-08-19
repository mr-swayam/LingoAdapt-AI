import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.course import ExerciseType
from app.models.progress import LessonAttemptStatus
from app.repositories import gamification_repository, progress_repository
from app.services import gamification_service
from tests.course_fixtures import SeededLesson, build_lesson_with_all_types
from tests.gamification_fixtures import seed_achievement_catalog


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


def _answer_all(
    client: TestClient, token: str, seeded: SeededLesson, attempt_id: str, *, last_wrong: bool
) -> dict:
    answers = {
        ExerciseType.MULTIPLE_CHOICE: {
            "option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])
        },
        ExerciseType.FILL_BLANK: {"text": "Hello"},
        ExerciseType.TRANSLATION: {"text": "Hello"},
        ExerciseType.WORD_ORDER: {
            "option_ids": [
                str(seeded.option_ids[ExerciseType.WORD_ORDER]["Good"]),
                str(seeded.option_ids[ExerciseType.WORD_ORDER]["morning"]),
            ]
        },
        ExerciseType.MATCHING: {
            "pairs": [
                {
                    "left_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["left1"]),
                    "right_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["right1"]),
                },
                {
                    "left_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["left2"]),
                    "right_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["right2"]),
                },
            ]
        },
    }
    if last_wrong:
        answers[ExerciseType.MATCHING] = {
            "pairs": [
                {
                    "left_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["left1"]),
                    "right_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["right2"]),
                },
            ]
        }

    last_response = None
    for ex_type, exercise_id in seeded.exercise_ids.items():
        last_response = client.post(
            f"/api/v1/exercises/{exercise_id}/answer",
            headers=_auth_headers(token),
            json={"lesson_attempt_id": attempt_id, "submitted_answer": answers[ex_type]},
        )
    assert last_response is not None
    return last_response.json()


def test_completing_a_lesson_awards_xp_proportional_to_correct_count(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    result = _answer_all(client, token, seeded, attempt_id, last_wrong=True)

    assert result["lesson_completed"] is True
    assert result["correct_count"] == 4
    assert result["xp_earned"] == 40  # 4 correct * 10 XP


def test_completing_a_lesson_sets_streak_to_one_on_first_activity(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    result = _answer_all(client, token, seeded, attempt_id, last_wrong=False)

    assert result["current_streak"] == 1


def test_incomplete_lesson_reports_zero_xp_and_no_streak(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    exercise_id = seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]
    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": attempt_id,
            "submitted_answer": {
                "option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])
            },
        },
    ).json()

    assert response["lesson_completed"] is False
    assert response["xp_earned"] == 0
    assert response["current_streak"] is None


def test_first_lesson_and_perfect_lesson_achievements_unlock(
    client: TestClient, db_session: Session
) -> None:
    seed_achievement_catalog(db_session)
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    result = _answer_all(client, token, seeded, attempt_id, last_wrong=False)

    assert set(result["new_achievements"]) == {"FIRST_LESSON", "PERFECT_LESSON"}


def test_imperfect_lesson_does_not_unlock_perfect_achievement(
    client: TestClient, db_session: Session
) -> None:
    seed_achievement_catalog(db_session)
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]

    result = _answer_all(client, token, seeded, attempt_id, last_wrong=True)

    assert result["new_achievements"] == ["FIRST_LESSON"]


def test_progress_endpoint_reflects_completed_lesson(
    client: TestClient, db_session: Session
) -> None:
    seed_achievement_catalog(db_session)
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]
    _answer_all(client, token, seeded, attempt_id, last_wrong=False)

    response = client.get("/api/v1/me/progress", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total_xp"] == 50  # 5 correct * 10 XP
    assert body["xp_today"] == 50
    assert body["daily_goal_xp"] == 50
    assert body["current_streak"] == 1
    assert body["longest_streak"] == 1
    assert body["course_progress"] == [
        {
            "course_id": body["course_progress"][0]["course_id"],
            "course_title": "Test Course",
            "completed_lessons": 1,
            "total_lessons": 1,
            "percent_complete": 100.0,
        }
    ]
    earned_codes = {a["code"] for a in body["achievements"] if a["earned"]}
    assert earned_codes == {"FIRST_LESSON", "PERFECT_LESSON"}
    assert len(body["recent_xp_transactions"]) == 1
    assert body["recent_xp_transactions"][0]["amount"] == 50


def test_progress_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me/progress")
    assert response.status_code == 401


def test_achievements_endpoint_lists_full_catalog_with_earned_flags(
    client: TestClient, db_session: Session
) -> None:
    seed_achievement_catalog(db_session)
    token = _signup_and_get_token(client)

    response = client.get("/api/v1/achievements", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    codes = {a["code"] for a in body}
    assert codes == {
        "FIRST_LESSON",
        "PERFECT_LESSON",
        "STREAK_3",
        "XP_100",
        "QUEST_MASTER",
        "FIRST_FRIEND",
        "RISING_STAR",
    }
    assert all(a["earned"] is False for a in body)


def test_apply_lesson_completion_rewards_is_idempotent(
    client: TestClient, db_session: Session
) -> None:
    """Direct service-level test of the concurrency safety net: calling
    apply_lesson_completion_rewards twice for the same attempt must not
    double-award XP. This path isn't reachable through the HTTP API alone
    (a completed attempt 409s on further answers), so it's exercised here
    at the service layer to prove the idempotency guard itself works.
    """
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    attempt_id = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()["lesson_attempt_id"]
    _answer_all(client, token, seeded, attempt_id, last_wrong=False)

    attempt = progress_repository.get_attempt(db_session, uuid.UUID(attempt_id))
    assert attempt is not None
    assert attempt.status == LessonAttemptStatus.COMPLETED

    first_total = gamification_repository.get_total_xp(db_session, attempt.user_id)

    second_call = gamification_service.apply_lesson_completion_rewards(
        db_session, user_id=attempt.user_id, attempt=attempt
    )
    db_session.commit()

    assert second_call.already_awarded is True
    assert second_call.new_achievements == []
    assert gamification_repository.get_total_xp(db_session, attempt.user_id) == first_total
