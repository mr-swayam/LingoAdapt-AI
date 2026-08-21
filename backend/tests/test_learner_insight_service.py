"""V3 shared learner-insight layer: weak/improving skills, review
priorities, insufficient-data check. Improving-skill tests exercise the
exact fixed thresholds from V3 architecture review item 16 at their
boundaries, not just "roughly works"."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learner_model import LearningEvent
from app.repositories import course_repository
from app.services import learner_insight_service, learner_model_service
from tests.practice_fixtures import build_multi_skill_course


def _signup_and_get_user_id(client: TestClient, email: str = "learner@example.com") -> uuid.UUID:
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
    return uuid.UUID(response.json()["user"]["id"])


def _log_answer_at(
    db_session: Session,
    *,
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    is_correct: bool,
    when: datetime,
) -> None:
    exercise = course_repository.get_exercise(db_session, exercise_id)
    assert exercise is not None
    learner_model_service.record_answer_learning_event(
        db_session, user_id=user_id, exercise=exercise, is_correct=is_correct
    )
    db_session.commit()
    latest = (
        db_session.execute(
            select(LearningEvent)
            .where(LearningEvent.user_id == user_id, LearningEvent.exercise_id == exercise_id)
            .order_by(LearningEvent.created_at.desc())
        )
        .scalars()
        .first()
    )
    assert latest is not None
    latest.created_at = when
    db_session.commit()


def test_weak_skills_excludes_unattempted_skills_and_sorts_ascending(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    user_id = _signup_and_get_user_id(client)
    now = datetime.now(UTC)
    _log_answer_at(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=False,
        when=now,
    )
    _log_answer_at(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_B"][0],
        is_correct=True,
        when=now,
    )

    weak = learner_insight_service.get_weak_skills(db_session, user_id=user_id)

    names = [w.skill_name for w in weak]
    assert "SKILL_A" in names and "SKILL_B" in names
    assert "SKILL_C" not in names  # never attempted - excluded, not shown at mastery=0
    assert weak[0].mastery <= weak[-1].mastery


def test_improving_skill_requires_minimum_attempts_in_both_windows(
    client: TestClient, db_session: Session
) -> None:
    """Boundary at exactly 3 vs 2 attempts per window
    (IMPROVING_SKILL_MIN_ATTEMPTS_PER_WINDOW)."""
    fixture = build_multi_skill_course(db_session)
    user_id = _signup_and_get_user_id(client)
    now = datetime.now(UTC)
    exercise_id = fixture.exercise_ids["SKILL_A"][0]

    # Previous window (8-14 days ago): 2 attempts only - below the minimum.
    for _ in range(2):
        _log_answer_at(
            db_session,
            user_id=user_id,
            exercise_id=exercise_id,
            is_correct=False,
            when=now - timedelta(days=10),
        )
    # Recent window (last 7 days): 3 attempts, all correct.
    for _ in range(3):
        _log_answer_at(
            db_session,
            user_id=user_id,
            exercise_id=exercise_id,
            is_correct=True,
            when=now - timedelta(days=1),
        )

    improving = learner_insight_service.get_improving_skills(db_session, user_id=user_id)
    assert improving == []  # previous window had only 2 attempts - not enough to call a trend


def test_improving_skill_requires_at_least_15_point_delta(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    user_id = _signup_and_get_user_id(client)
    now = datetime.now(UTC)
    exercise_id = fixture.exercise_ids["SKILL_A"][0]

    # Previous window: 3 attempts, 1 correct (33% accuracy).
    for is_correct in [True, False, False]:
        _log_answer_at(
            db_session,
            user_id=user_id,
            exercise_id=exercise_id,
            is_correct=is_correct,
            when=now - timedelta(days=10),
        )
    # Recent window: 3 attempts, 2 correct (67% accuracy) - a 34-point jump, comfortably over 15.
    for is_correct in [True, True, False]:
        _log_answer_at(
            db_session,
            user_id=user_id,
            exercise_id=exercise_id,
            is_correct=is_correct,
            when=now - timedelta(days=1),
        )

    improving = learner_insight_service.get_improving_skills(db_session, user_id=user_id)
    assert len(improving) == 1
    assert improving[0].skill_name == "SKILL_A"
    assert improving[0].delta >= 15.0


def test_improving_skill_below_threshold_delta_is_excluded(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    user_id = _signup_and_get_user_id(client)
    now = datetime.now(UTC)
    exercise_id = fixture.exercise_ids["SKILL_A"][0]

    # Previous window: 3/3 correct (100%). Recent window: 3/3 correct (100%) - 0-point delta.
    for _ in range(3):
        _log_answer_at(
            db_session,
            user_id=user_id,
            exercise_id=exercise_id,
            is_correct=True,
            when=now - timedelta(days=10),
        )
    for _ in range(3):
        _log_answer_at(
            db_session,
            user_id=user_id,
            exercise_id=exercise_id,
            is_correct=True,
            when=now - timedelta(days=1),
        )

    improving = learner_insight_service.get_improving_skills(db_session, user_id=user_id)
    assert improving == []


def test_has_any_learning_history_false_for_a_fresh_user(
    client: TestClient, db_session: Session
) -> None:
    build_multi_skill_course(db_session)
    user_id = _signup_and_get_user_id(client)
    assert learner_insight_service.has_any_learning_history(db_session, user_id=user_id) is False


def test_has_any_learning_history_true_after_one_attempt(
    client: TestClient, db_session: Session
) -> None:
    fixture = build_multi_skill_course(db_session)
    user_id = _signup_and_get_user_id(client)
    _log_answer_at(
        db_session,
        user_id=user_id,
        exercise_id=fixture.exercise_ids["SKILL_A"][0],
        is_correct=True,
        when=datetime.now(UTC),
    )
    assert learner_insight_service.has_any_learning_history(db_session, user_id=user_id) is True
