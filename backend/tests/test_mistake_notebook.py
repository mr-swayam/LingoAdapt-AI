"""V3.3 Mistake Notebook: unified listing across LESSON/PRACTICE/TUTOR,
Type A/B repeated-mistake grouping (architecture review item 5), pagination
correctness (item 8), and "Practice Again" incl. the exercise_id ownership
check (item 17) and its interaction with an existing in-progress session
(item 6).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories import course_repository
from app.schemas.mistakes import MistakeOut, MistakeSource, RepeatedMistakeType
from app.services import mistake_service
from app.services.learner_model_service import record_answer_learning_event
from tests.ai_fixtures import FakeAIProvider
from tests.conversation_fixtures import build_grammar_skills
from tests.practice_fixtures import build_multi_skill_course
from tests.short_answer_fixtures import build_short_answer_lesson


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


def _answer_wrong_via_lesson(
    client: TestClient, db_session: Session, *, token: str, exercise_id: uuid.UUID
) -> None:
    """Answers `exercise_id` wrong, then answers every other exercise in the
    same lesson (correctly) so the LessonAttempt reaches COMPLETED. Without
    this, a second call for the same exercise_id would reuse the still-
    IN_PROGRESS attempt from the first call and hit submit_answer's
    idempotent-resubmission short-circuit instead of recording a genuinely
    new, distinct wrong ExerciseAttempt - start_lesson only creates a fresh
    attempt when no IN_PROGRESS one exists, unlike practice-again (V3),
    which always creates a fresh PracticeSession."""
    exercise = course_repository.get_exercise(db_session, exercise_id)
    assert exercise is not None
    lesson = course_repository.get_lesson(db_session, exercise.lesson_id)
    assert lesson is not None
    start = client.post(
        f"/api/v1/lessons/{exercise.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    already_answered = set(start["answered_exercise_ids"])

    for ex in lesson.exercises:
        if str(ex.id) in already_answered:
            continue
        # build_multi_skill_course only ever produces MULTIPLE_CHOICE
        # exercises, so every option is unambiguously correct or wrong.
        wrong_option = next(opt for opt in ex.options if not opt.is_correct)
        correct_option = next(opt for opt in ex.options if opt.is_correct)
        chosen = wrong_option if ex.id == exercise_id else correct_option
        submitted = {"option_id": str(chosen.id)}
        client.post(
            f"/api/v1/exercises/{ex.id}/answer",
            headers=_auth_headers(token),
            json={"lesson_attempt_id": start["lesson_attempt_id"], "submitted_answer": submitted},
        )


def _answer_wrong_via_practice(
    client: TestClient, db_session: Session, *, token: str, skill_id: uuid.UUID
) -> uuid.UUID:
    """Targets a skill (not a specific exercise_id - that's _select_
    exercise_for_skill's call, same as any other practice session) via a
    fresh practice-again session, answers whichever exercise it selects
    wrong, and returns that exercise's id. Calling this twice in a row for
    the same skill_id deterministically re-serves the same exercise the
    second time (mistake-review-priority - see _select_exercise_for_skill),
    which is what the repeated-mistake tests below rely on."""
    start = client.post(
        "/api/v1/practice/practice-again",
        headers=_auth_headers(token),
        json={"skill_id": str(skill_id)},
    ).json()
    session_id = start["practice_session_id"]
    picked = start["exercises"][0]
    picked_exercise_id = uuid.UUID(picked["id"])
    exercise = course_repository.get_exercise(db_session, picked_exercise_id)
    assert exercise is not None
    wrong_option_id = str(next(opt for opt in exercise.options if not opt.is_correct).id)
    client.post(
        f"/api/v1/practice/{session_id}/answer",
        headers=_auth_headers(token),
        json={
            "exercise_id": str(picked_exercise_id),
            "submitted_answer": {"option_id": wrong_option_id},
        },
    )
    return picked_exercise_id


# --- Pure grouping logic (Type A vs Type B - architecture review item 5) ---


def _mistake(
    *, skill_id: uuid.UUID, exercise_id: uuid.UUID | None, created_at: datetime
) -> MistakeOut:
    return MistakeOut(
        id=uuid.uuid4(),
        source=MistakeSource.LESSON if exercise_id else MistakeSource.TUTOR,
        skill_id=skill_id,
        skill_name="Test Skill",
        exercise_id=exercise_id,
        exercise_type="MULTIPLE_CHOICE" if exercise_id else None,
        prompt="prompt" if exercise_id else None,
        submitted_text="wrong",
        correct_text="right" if exercise_id else None,
        explanation=None,
        category=None,
        created_at=created_at,
    )


def test_two_wrong_attempts_on_the_same_exercise_form_a_type_b_group() -> None:
    skill_id = uuid.uuid4()
    exercise_id = uuid.uuid4()
    now = datetime.now(UTC)
    records = [
        _mistake(skill_id=skill_id, exercise_id=exercise_id, created_at=now),
        _mistake(skill_id=skill_id, exercise_id=exercise_id, created_at=now - timedelta(days=1)),
    ]

    groups = mistake_service.group_repeated_mistakes(records)

    assert len(groups) == 1
    assert groups[0].type == RepeatedMistakeType.REPEATED_EXACT_MISTAKE
    assert groups[0].exercise_id == exercise_id
    assert groups[0].count == 2


def test_wrong_attempts_on_different_exercises_same_skill_form_a_type_a_group_only() -> None:
    skill_id = uuid.uuid4()
    now = datetime.now(UTC)
    records = [
        _mistake(skill_id=skill_id, exercise_id=uuid.uuid4(), created_at=now),
        _mistake(skill_id=skill_id, exercise_id=uuid.uuid4(), created_at=now - timedelta(days=1)),
    ]

    groups = mistake_service.group_repeated_mistakes(records)

    assert len(groups) == 1
    assert groups[0].type == RepeatedMistakeType.REPEATED_DIFFICULTY
    assert groups[0].exercise_id is None
    assert groups[0].count == 2


def test_a_skill_fully_explained_by_one_repeated_exercise_does_not_also_get_a_type_a_group() -> (
    None
):
    """3 wrong attempts, all on the same exercise: Type B fires; Type A must
    not also fire for the same underlying facts under a second label."""
    skill_id = uuid.uuid4()
    exercise_id = uuid.uuid4()
    now = datetime.now(UTC)
    records = [
        _mistake(skill_id=skill_id, exercise_id=exercise_id, created_at=now - timedelta(days=i))
        for i in range(3)
    ]

    groups = mistake_service.group_repeated_mistakes(records)

    assert len(groups) == 1
    assert groups[0].type == RepeatedMistakeType.REPEATED_EXACT_MISTAKE
    assert groups[0].count == 3


def test_two_wrong_attempts_split_between_one_exercise_and_a_tutor_mistake_form_type_a() -> None:
    """A TUTOR mistake has no exercise_id - it still counts as its own
    distinct "occasion" for Type A grouping (repeated difficulty in a
    skill), even though it can never contribute to a Type B group."""
    skill_id = uuid.uuid4()
    now = datetime.now(UTC)
    records = [
        _mistake(skill_id=skill_id, exercise_id=uuid.uuid4(), created_at=now),
        _mistake(skill_id=skill_id, exercise_id=None, created_at=now - timedelta(days=1)),
    ]

    groups = mistake_service.group_repeated_mistakes(records)

    assert len(groups) == 1
    assert groups[0].type == RepeatedMistakeType.REPEATED_DIFFICULTY


def test_a_single_mistake_forms_no_group() -> None:
    records = [
        _mistake(skill_id=uuid.uuid4(), exercise_id=uuid.uuid4(), created_at=datetime.now(UTC))
    ]
    assert mistake_service.group_repeated_mistakes(records) == []


# --- Real LESSON/PRACTICE sources, via the actual HTTP flow ---


def test_wrong_lesson_answer_appears_in_the_mistake_list(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    exercise_id = fixture.exercise_ids["SKILL_A"][0]
    _answer_wrong_via_lesson(client, db_session, token=token, exercise_id=exercise_id)

    body = client.get("/api/v1/me/mistakes", headers=_auth_headers(token)).json()

    assert body["items"], "the wrong lesson answer must show up as a mistake"
    item = body["items"][0]
    assert item["source"] == "LESSON"
    assert item["exercise_id"] == str(exercise_id)
    assert item["correct_text"]  # deterministic types always resolve a real correct answer


def test_wrong_practice_answer_appears_in_the_mistake_list(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    exercise_id = _answer_wrong_via_practice(
        client, db_session, token=token, skill_id=fixture.skill_ids["SKILL_A"]
    )

    body = client.get(
        "/api/v1/me/mistakes", headers=_auth_headers(token), params={"source": "PRACTICE"}
    ).json()

    assert len(body["items"]) == 1
    assert body["items"][0]["source"] == "PRACTICE"
    assert body["items"][0]["exercise_id"] == str(exercise_id)


def test_mistakes_are_isolated_per_user(client: TestClient, db_session: Session) -> None:
    fixture = build_multi_skill_course(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    _answer_wrong_via_lesson(
        client, db_session, token=token_a, exercise_id=fixture.exercise_ids["SKILL_A"][0]
    )

    token_b = _signup_and_get_token(client, email="b@example.com")
    body_b = client.get("/api/v1/me/mistakes", headers=_auth_headers(token_b)).json()

    assert body_b["items"] == []


def test_skill_id_filter_excludes_other_skills(client: TestClient, db_session: Session) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    _answer_wrong_via_lesson(
        client, db_session, token=token, exercise_id=fixture.exercise_ids["SKILL_A"][0]
    )
    _answer_wrong_via_lesson(
        client, db_session, token=token, exercise_id=fixture.exercise_ids["SKILL_B"][0]
    )

    body = client.get(
        "/api/v1/me/mistakes",
        headers=_auth_headers(token),
        params={"skill_id": str(fixture.skill_ids["SKILL_A"])},
    ).json()

    assert len(body["items"]) == 1
    assert body["items"][0]["skill_name"] == "SKILL_A"


def test_pagination_across_interleaved_sources_has_no_gaps_or_duplicates(
    client: TestClient, db_session: Session
) -> None:
    """2 LESSON + 2 PRACTICE mistakes, created in an interleaved order so a
    naive per-source fixed-window/offset implementation could plausibly
    misalign at a page boundary. Paginating with limit=2 across pages must
    reconstruct the full set with no gaps or duplicates, and has_more must
    be accurate at every step (architecture review item 8)."""
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    skill_a = fixture.exercise_ids["SKILL_A"]

    # Interleave LESSON/PRACTICE creation order.
    _answer_wrong_via_lesson(client, db_session, token=token, exercise_id=skill_a[0])
    _answer_wrong_via_practice(
        client, db_session, token=token, skill_id=fixture.skill_ids["SKILL_B"]
    )
    _answer_wrong_via_lesson(client, db_session, token=token, exercise_id=skill_a[1])
    _answer_wrong_via_practice(
        client, db_session, token=token, skill_id=fixture.skill_ids["SKILL_C"]
    )

    all_body = client.get(
        "/api/v1/me/mistakes", headers=_auth_headers(token), params={"limit": 100}
    ).json()
    all_ids = [item["id"] for item in all_body["items"]]
    assert len(all_ids) == 4
    assert all_body["has_more"] is False

    seen: list[str] = []
    offset = 0
    while True:
        page = client.get(
            "/api/v1/me/mistakes",
            headers=_auth_headers(token),
            params={"limit": 2, "offset": offset},
        ).json()
        seen.extend(item["id"] for item in page["items"])
        if not page["has_more"]:
            break
        offset += 2

    assert seen == all_ids  # same order, no gaps, no duplicates, across the exact page boundaries


# --- TUTOR source: only genuine conversation mistakes, never SHORT_ANSWER
# exercise sub-errors (a real discrepancy found against the plan's original
# assumption - see mistake_repository/evaluation_repository for the fix). ---


def test_short_answer_exercise_mistake_is_not_double_counted_as_a_tutor_mistake(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    fixture = build_short_answer_lesson(db_session)
    fake_ai_provider.queue_evaluation(
        is_correct=False,
        score=0.1,
        explanation="Missing a verb.",
        corrected_answer="corrected",
        errors=[{"type": "grammar", "skill": "missing verb", "severity": "medium"}],
    )
    token = _signup_and_get_token(client)
    start = client.post(
        f"/api/v1/lessons/{fixture.lesson_id}/start", headers=_auth_headers(token)
    ).json()
    client.post(
        f"/api/v1/exercises/{fixture.exercise_id}/answer",
        headers=_auth_headers(token),
        json={"lesson_attempt_id": start["lesson_attempt_id"], "submitted_answer": {"text": "x"}},
    )

    body = client.get("/api/v1/me/mistakes", headers=_auth_headers(token)).json()

    assert len(body["items"]) == 1  # the LESSON mistake itself
    assert body["items"][0]["source"] == "LESSON"
    # Not present a second time mislabeled as TUTOR:
    assert not any(item["source"] == "TUTOR" for item in body["items"])


def test_genuine_tutor_conversation_mistake_appears_with_no_correct_text(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_grammar_skills(db_session)
    fake_ai_provider.queue_conversation_turn(
        reply="Got it!",
        corrections=[
            {
                "original": "I go there yesterday",
                "corrected": "I went there yesterday",
                "explanation": "Use past tense.",
                "skill": "past tense",
            }
        ],
    )
    token = _signup_and_get_token(client)
    conversation = client.post(
        "/api/v1/tutor/conversations", headers=_auth_headers(token), json={"scenario": "RESTAURANT"}
    ).json()
    client.post(
        f"/api/v1/tutor/conversations/{conversation['id']}/messages",
        headers=_auth_headers(token),
        json={"text": "I go there yesterday"},
    )

    body = client.get(
        "/api/v1/me/mistakes", headers=_auth_headers(token), params={"source": "TUTOR"}
    ).json()

    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["source"] == "TUTOR"
    assert item["exercise_id"] is None
    assert item["correct_text"] is None  # honestly never available - never fabricated
    assert item["submitted_text"] == "I go there yesterday"


# --- Practice Again: skill_id vs exercise_id, ownership, session interaction ---


def test_practice_again_with_exercise_id_serves_exactly_that_exercise(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    exercise_id = fixture.exercise_ids["SKILL_A"][0]
    _answer_wrong_via_lesson(client, db_session, token=token, exercise_id=exercise_id)

    response = client.post(
        "/api/v1/practice/practice-again",
        headers=_auth_headers(token),
        json={"exercise_id": str(exercise_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert [ex["id"] for ex in body["exercises"]] == [str(exercise_id)]


def test_practice_again_with_exercise_id_rejects_an_exercise_that_is_not_a_past_mistake(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    never_missed_exercise_id = fixture.exercise_ids["SKILL_A"][0]

    response = client.post(
        "/api/v1/practice/practice-again",
        headers=_auth_headers(token),
        json={"exercise_id": str(never_missed_exercise_id)},
    )

    assert response.status_code == 400


def test_practice_again_with_exercise_id_rejects_another_users_mistake(
    client: TestClient, db_session: Session
) -> None:
    """Architecture review item 17: exercise_id is client-supplied for this
    entry point - user B must not be able to "retry" using an exercise_id
    that is genuinely a mistake, but belongs to user A's history, not theirs."""
    fixture = build_multi_skill_course(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    exercise_id = fixture.exercise_ids["SKILL_A"][0]
    _answer_wrong_via_lesson(client, db_session, token=token_a, exercise_id=exercise_id)

    token_b = _signup_and_get_token(client, email="b@example.com")
    response = client.post(
        "/api/v1/practice/practice-again",
        headers=_auth_headers(token_b),
        json={"exercise_id": str(exercise_id)},
    )

    assert response.status_code == 400


def test_practice_again_with_skill_id_does_not_require_ownership_of_a_specific_exercise(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/practice/practice-again",
        headers=_auth_headers(token),
        json={"skill_id": str(fixture.skill_ids["SKILL_A"])},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["exercises"][0]["id"] in {str(x) for x in fixture.exercise_ids["SKILL_A"]}


def test_practice_again_abandons_an_existing_general_in_progress_session(
    client: TestClient, db_session: Session
) -> None:
    """practice_repository.get_in_progress_session assumes at most one
    IN_PROGRESS session per user - starting a targeted session while a
    general one is still open must not leave two, or a later call to
    /practice/start would crash (scalar_one_or_none on 2 rows)."""
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    user_id = uuid.UUID(client.get("/api/v1/me", headers=_auth_headers(token)).json()["id"])
    # A fresh user with zero history gets an immediately-COMPLETED empty
    # session (see test_practice.py's own test of that behavior) - some
    # real mastery history is needed first so /practice/start actually
    # produces a genuine multi-exercise IN_PROGRESS session to abandon.
    exercise = course_repository.get_exercise(db_session, fixture.exercise_ids["SKILL_B"][0])
    assert exercise is not None
    record_answer_learning_event(db_session, user_id=user_id, exercise=exercise, is_correct=True)
    db_session.commit()

    general = client.post("/api/v1/practice/start", headers=_auth_headers(token)).json()
    assert general["status"] == "IN_PROGRESS"

    targeted = client.post(
        "/api/v1/practice/practice-again",
        headers=_auth_headers(token),
        json={"skill_id": str(fixture.skill_ids["SKILL_A"])},
    ).json()
    assert targeted["practice_session_id"] != general["practice_session_id"]

    # Must not raise (would be a 500 if two IN_PROGRESS sessions existed).
    resumed = client.post("/api/v1/practice/start", headers=_auth_headers(token))
    assert resumed.status_code == 200
    assert resumed.json()["practice_session_id"] == targeted["practice_session_id"]


def test_practice_again_requires_exactly_one_of_skill_id_or_exercise_id(
    client: TestClient, db_session: Session
) -> None:
    build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)

    neither = client.post(
        "/api/v1/practice/practice-again", headers=_auth_headers(token), json={}
    )
    assert neither.status_code == 422

    both = client.post(
        "/api/v1/practice/practice-again",
        headers=_auth_headers(token),
        json={"skill_id": str(uuid.uuid4()), "exercise_id": str(uuid.uuid4())},
    )
    assert both.status_code == 422


def test_repeated_mistakes_endpoint_returns_a_type_b_group_for_a_twice_missed_exercise(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    token = _signup_and_get_token(client)
    exercise_id = fixture.exercise_ids["SKILL_A"][0]
    _answer_wrong_via_lesson(client, db_session, token=token, exercise_id=exercise_id)
    _answer_wrong_via_lesson(client, db_session, token=token, exercise_id=exercise_id)

    body = client.get("/api/v1/me/mistakes/repeated", headers=_auth_headers(token)).json()

    assert len(body) == 1
    assert body[0]["type"] == "REPEATED_EXACT_MISTAKE"
    assert body[0]["exercise_id"] == str(exercise_id)
    assert body[0]["count"] == 2
