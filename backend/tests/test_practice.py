import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories import course_repository
from app.services.learner_model_service import record_answer_learning_event
from tests.practice_fixtures import build_multi_skill_course


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


def _user_id(client: TestClient, token: str) -> uuid.UUID:
    me = client.get("/api/v1/me", headers=_auth_headers(token)).json()
    return uuid.UUID(me["id"])


def _practice_n_times(
    db_session: Session,
    *,
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    is_correct: bool,
    times: int,
) -> None:
    exercise = course_repository.get_exercise(db_session, exercise_id)
    assert exercise is not None
    for _ in range(times):
        record_answer_learning_event(
            db_session, user_id=user_id, exercise=exercise, is_correct=is_correct
        )
    db_session.commit()


def test_practice_session_is_empty_for_a_user_with_no_history(
    client: TestClient, db_session: Session
) -> None:
    build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)

    response = client.post("/api/v1/practice/start", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 0
    assert body["exercises"] == []
    assert body["status"] == "COMPLETED"


def test_practice_prioritizes_the_weakest_skill_first(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)

    # SKILL_A: barely practiced, low mastery. SKILL_B: heavily practiced, high mastery.
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_B"][0],
        is_correct=True,
        times=20,
    )

    body = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()

    skill_a_exercise_ids = {str(x) for x in fixture.exercise_ids["SKILL_A"]}
    skill_b_exercise_ids = {str(x) for x in fixture.exercise_ids["SKILL_B"]}
    positions = {
        ex["id"]: i
        for i, ex in enumerate(body["exercises"])
        if ex["id"] in skill_a_exercise_ids | skill_b_exercise_ids
    }
    skill_a_position = min(pos for eid, pos in positions.items() if eid in skill_a_exercise_ids)
    skill_b_position = min(pos for eid, pos in positions.items() if eid in skill_b_exercise_ids)
    assert skill_a_position < skill_b_position


def test_two_users_with_different_histories_get_different_practice_sets(
    client: TestClient, db_session: Session
) -> None:
    """The Phase 5 exit criteria, proven directly."""
    fixture = build_multi_skill_course(db_session)

    token_a = _signup_and_get_token(client, email="a@example.com")
    user_a = _user_id(client, token_a)
    _practice_n_times(
        db_session,
        user_id=user_a,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )
    _practice_n_times(
        db_session,
        user_id=user_a,
        exercise_id=fixture.exercise_ids["SKILL_B"][0],
        is_correct=True,
        times=20,
    )

    token_b = _signup_and_get_token(client, email="b@example.com")
    user_b = _user_id(client, token_b)
    _practice_n_times(
        db_session,
        user_id=user_b,
        exercise_id=fixture.exercise_ids["SKILL_B"][0],
        is_correct=True,
        times=1,
    )
    _practice_n_times(
        db_session,
        user_id=user_b,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=20,
    )

    body_a = client.post("/api/v1/practice/start", headers=_auth_headers(token_a)).json()
    body_b = client.post("/api/v1/practice/start", headers=_auth_headers(token_b)).json()

    first_exercise_a = body_a["exercises"][0]["id"]
    first_exercise_b = body_b["exercises"][0]["id"]
    assert first_exercise_a != first_exercise_b
    assert first_exercise_a in {str(x) for x in fixture.exercise_ids["SKILL_A"]}
    assert first_exercise_b in {str(x) for x in fixture.exercise_ids["SKILL_B"]}


def test_mistake_review_overrides_difficulty_matching(
    client: TestClient, db_session: Session
) -> None:
    """User ends up with high mastery on SKILL_A (favoring the hard 0.8
    exercise by difficulty-matching alone), but missed the easy 0.2 exercise
    at some point - mistake review should still re-serve that easy one.
    """
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)

    easy_exercise_id, hard_exercise_id = fixture.exercise_ids["SKILL_A"]
    _practice_n_times(
        db_session, user_id=user_id, exercise_id=easy_exercise_id, is_correct=False, times=1
    )
    _practice_n_times(
        db_session, user_id=user_id, exercise_id=hard_exercise_id, is_correct=True, times=20
    )

    body = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()

    skill_a_ids = {str(x) for x in fixture.exercise_ids["SKILL_A"]}
    selected = next(ex["id"] for ex in body["exercises"] if ex["id"] in skill_a_ids)
    assert selected == str(easy_exercise_id)


def test_answering_a_practice_question_updates_skill_mastery(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )

    start = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    session_id = start["practice_session_id"]
    exercise = start["exercises"][0]
    skill_code = next(
        code for code, ids in fixture.exercise_ids.items() if uuid.UUID(exercise["id"]) in ids
    )
    correct_option_id = str(fixture.options[uuid.UUID(exercise["id"])].correct)

    response = client.post(
        f"/api/v1/practice/{session_id}/answer",
        headers=_auth_headers(token),
        json={
            "exercise_id": exercise["id"],
            "submitted_answer": {"option_id": correct_option_id},
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is True

    mastery_body = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    matching_skill = next(s for s in mastery_body if s["skill_code"] == skill_code)
    assert matching_skill["attempt_count"] >= 2  # the seed answer + this one


def test_resubmitting_a_practice_question_does_not_double_count(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )

    start = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    session_id = start["practice_session_id"]
    exercise = start["exercises"][0]
    correct_option_id = str(fixture.options[uuid.UUID(exercise["id"])].correct)
    payload = {
        "exercise_id": exercise["id"],
        "submitted_answer": {"option_id": correct_option_id},
    }

    client.post(f"/api/v1/practice/{session_id}/answer", headers=_auth_headers(token), json=payload)
    client.post(f"/api/v1/practice/{session_id}/answer", headers=_auth_headers(token), json=payload)

    skill_code = next(
        code for code, ids in fixture.exercise_ids.items() if uuid.UUID(exercise["id"]) in ids
    )
    mastery_body = client.get("/api/v1/me/mastery", headers=_auth_headers(token)).json()
    matching_skill = next(s for s in mastery_body if s["skill_code"] == skill_code)
    assert matching_skill["attempt_count"] == 2  # seed answer + one real practice answer, not two


def test_practice_session_completes_after_all_questions_answered(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)
    for skill in ["SKILL_A", "SKILL_B", "SKILL_C"]:
        _practice_n_times(
            db_session,
            user_id=user_id,
            exercise_id=fixture.exercise_ids[skill][0],
            is_correct=True,
            times=1,
        )

    start = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    session_id = start["practice_session_id"]

    last_response = None
    for exercise in start["exercises"]:
        correct_option_id = str(fixture.options[uuid.UUID(exercise["id"])].correct)
        last_response = client.post(
            f"/api/v1/practice/{session_id}/answer",
            headers=_auth_headers(token),
            json={
                "exercise_id": exercise["id"],
                "submitted_answer": {"option_id": correct_option_id},
            },
        ).json()

    assert last_response is not None
    assert last_response["session_completed"] is True
    assert last_response["correct_count"] == start["total_count"]


def test_resuming_practice_returns_the_same_in_progress_session(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )

    first = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    second = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()

    assert first["practice_session_id"] == second["practice_session_id"]


def test_answering_someone_elses_practice_session_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    user_a = _user_id(client, token_a)
    _practice_n_times(
        db_session,
        user_id=user_a,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )
    start = client.post("/api/v1/practice/start", headers=_auth_headers(token_a)).json()

    token_b = _signup_and_get_token(client, email="b@example.com")
    exercise = start["exercises"][0]
    response = client.post(
        f"/api/v1/practice/{start['practice_session_id']}/answer",
        headers=_auth_headers(token_b),
        json={
            "exercise_id": exercise["id"],
            "submitted_answer": {
                "option_id": str(fixture.options[uuid.UUID(exercise["id"])].correct)
            },
        },
    )

    assert response.status_code == 403


def test_practice_start_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/practice/start")
    assert response.status_code == 401


def test_practice_reasons_reflect_real_mastery_and_skill_name(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)

    # SKILL_A: barely practiced (low mastery, weak). SKILL_B: heavily
    # practiced (high mastery, strong) - the reason for each exercise must
    # reflect this real difference, not a placeholder.
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_B"][0],
        is_correct=True,
        times=20,
    )

    body = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()

    skill_a_ids = {str(x) for x in fixture.exercise_ids["SKILL_A"]}
    skill_b_ids = {str(x) for x in fixture.exercise_ids["SKILL_B"]}
    skill_a_exercise = next(ex for ex in body["exercises"] if ex["id"] in skill_a_ids)
    skill_b_exercise = next(ex for ex in body["exercises"] if ex["id"] in skill_b_ids)
    reason_a = body["reasons"][skill_a_exercise["id"]]
    reason_b = body["reasons"][skill_b_exercise["id"]]

    assert reason_a["skill_name"]
    assert reason_b["skill_name"]
    assert reason_a["skill_name"] != reason_b["skill_name"]
    assert reason_a["mastery"] < reason_b["mastery"]


def test_practice_reasons_are_present_when_resuming_an_in_progress_session(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = _user_id(client, token)
    _practice_n_times(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        times=1,
    )

    client.post("/api/v1/practice/start", headers=_auth_headers(token))
    second = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()

    assert second["reasons"], "resumed session must still carry real reasons, not an empty map"
    for exercise in second["exercises"]:
        assert exercise["id"] in second["reasons"]
        assert second["reasons"][exercise["id"]]["skill_name"]
