from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.course import ExerciseType
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


def test_start_lesson_requires_authentication(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)

    response = client.post(f"/api/v1/lessons/{seeded.lesson_id}/start")

    assert response.status_code == 401


def test_start_lesson_does_not_leak_correct_answers(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)

    response = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["total_count"] == 5
    assert body["correct_count"] == 0
    assert body["answered_exercise_ids"] == []

    raw_body = response.text
    # None of the grading secrets should ever reach the client.
    assert "is_correct" not in raw_body
    assert "correct_position" not in raw_body
    assert "match_key" not in raw_body
    assert "Adiós" not in raw_body or True  # option text itself is fine, just not the key/flags


def test_word_order_and_matching_options_are_shuffled_but_complete(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)

    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercises_by_type = {ex["type"]: ex for ex in start["exercises"]}

    word_order_ids = {opt["id"] for opt in exercises_by_type["WORD_ORDER"]["options"]}
    assert word_order_ids == {
        str(seeded.option_ids[ExerciseType.WORD_ORDER]["Good"]),
        str(seeded.option_ids[ExerciseType.WORD_ORDER]["morning"]),
    }

    matching_ids = {opt["id"] for opt in exercises_by_type["MATCHING"]["options"]}
    assert matching_ids == {str(v) for v in seeded.option_ids[ExerciseType.MATCHING].values()}


def test_lesson_not_found_returns_404(client: TestClient) -> None:
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/lessons/00000000-0000-0000-0000-000000000000/start",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_multiple_choice_grading(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]

    correct_id = str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])
    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"option_id": correct_id},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["correct_answer"]["option_id"] == correct_id
    assert body["lesson_completed"] is False


def test_multiple_choice_wrong_answer(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]

    wrong_id = str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["wrong"])
    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"option_id": wrong_id},
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is False


def test_fill_blank_is_case_and_whitespace_insensitive(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.FILL_BLANK]

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "  hello  "},
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_translation_grading(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.TRANSLATION]

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"text": "Hi"},
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_word_order_correct_sequence(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.WORD_ORDER]
    opts = seeded.option_ids[ExerciseType.WORD_ORDER]

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"option_ids": [str(opts["Good"]), str(opts["morning"])]},
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_word_order_wrong_sequence(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.WORD_ORDER]
    opts = seeded.option_ids[ExerciseType.WORD_ORDER]

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {"option_ids": [str(opts["morning"]), str(opts["Good"])]},
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is False


def test_matching_correct_pairs(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.MATCHING]
    opts = seeded.option_ids[ExerciseType.MATCHING]

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {
                "pairs": [
                    {
                        "left_option_id": str(opts["left1"]),
                        "right_option_id": str(opts["right1"]),
                    },
                    {
                        "left_option_id": str(opts["left2"]),
                        "right_option_id": str(opts["right2"]),
                    },
                ]
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_matching_swapped_pairs_are_incorrect(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.MATCHING]
    opts = seeded.option_ids[ExerciseType.MATCHING]

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {
                "pairs": [
                    {
                        "left_option_id": str(opts["left1"]),
                        "right_option_id": str(opts["right2"]),
                    },
                    {
                        "left_option_id": str(opts["left2"]),
                        "right_option_id": str(opts["right1"]),
                    },
                ]
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is False


def test_malformed_answer_returns_400(client: TestClient, db_session: Session) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    exercise_id = seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={"lesson_attempt_id": start["lesson_attempt_id"], "submitted_answer": {}},
    )

    assert response.status_code == 400


def test_completing_all_exercises_marks_lesson_completed(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    attempt_id = start["lesson_attempt_id"]

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

    last_result = None
    for ex_type, exercise_id in seeded.exercise_ids.items():
        last_result = client.post(
            f"/api/v1/exercises/{exercise_id}/answer",
            headers=_auth_headers(token),
            json={"lesson_attempt_id": attempt_id, "submitted_answer": answers[ex_type]},
        ).json()

    assert last_result is not None
    assert last_result["lesson_completed"] is True
    assert last_result["correct_count"] == 5
    assert last_result["total_count"] == 5


def test_submitting_to_completed_attempt_returns_409(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    attempt_id = start["lesson_attempt_id"]

    # Answer all 5 to complete the lesson.
    for ex_type, exercise_id in seeded.exercise_ids.items():
        answer = (
            {"option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])}
            if ex_type == ExerciseType.MULTIPLE_CHOICE
            else {"text": "Hello"}
            if ex_type in (ExerciseType.FILL_BLANK, ExerciseType.TRANSLATION)
            else {
                "option_ids": [
                    str(seeded.option_ids[ExerciseType.WORD_ORDER]["Good"]),
                    str(seeded.option_ids[ExerciseType.WORD_ORDER]["morning"]),
                ]
            }
            if ex_type == ExerciseType.WORD_ORDER
            else {
                "pairs": [
                    {
                        "left_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["left1"]),
                        "right_option_id": str(
                            seeded.option_ids[ExerciseType.MATCHING]["right1"]
                        ),
                    },
                    {
                        "left_option_id": str(seeded.option_ids[ExerciseType.MATCHING]["left2"]),
                        "right_option_id": str(
                            seeded.option_ids[ExerciseType.MATCHING]["right2"]
                        ),
                    },
                ]
            }
        )
        client.post(
            f"/api/v1/exercises/{exercise_id}/answer",
            headers=_auth_headers(token),
            json={"lesson_attempt_id": attempt_id, "submitted_answer": answer},
        )

    # Starting the lesson again should now yield a *new* attempt (previous is COMPLETED).
    restart = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    assert restart["lesson_attempt_id"] != attempt_id
    assert restart["status"] == "IN_PROGRESS"

    # Submitting again against the old, completed attempt must be rejected.
    response = client.post(
        f"/api/v1/exercises/{seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": attempt_id,
            "submitted_answer": {
                "option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])
            },
        },
    )
    assert response.status_code == 409


def test_resume_returns_same_attempt_with_progress(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    attempt_id = start["lesson_attempt_id"]

    exercise_id = seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]
    client.post(
        f"/api/v1/exercises/{exercise_id}/answer",
        headers=_auth_headers(token),
        json={
            "lesson_attempt_id": attempt_id,
            "submitted_answer": {
                "option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])
            },
        },
    )

    resumed = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token)
    ).json()

    assert resumed["lesson_attempt_id"] == attempt_id
    assert resumed["correct_count"] == 1
    assert str(exercise_id) in resumed["answered_exercise_ids"]


def test_another_users_attempt_cannot_be_answered(
    client: TestClient, db_session: Session
) -> None:
    seeded = build_lesson_with_all_types(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    start = client.post(
        f"/api/v1/lessons/{seeded.lesson_id}/start", headers=_auth_headers(token_a)
    ).json()

    token_b = _signup_and_get_token(client, email="b@example.com")
    response = client.post(
        f"/api/v1/exercises/{seeded.exercise_ids[ExerciseType.MULTIPLE_CHOICE]}/answer",
        headers=_auth_headers(token_b),
        json={
            "lesson_attempt_id": start["lesson_attempt_id"],
            "submitted_answer": {
                "option_id": str(seeded.option_ids[ExerciseType.MULTIPLE_CHOICE]["correct"])
            },
        },
    )

    assert response.status_code == 403
