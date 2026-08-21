"""V3.1 AI Learning Coach: insufficient-data short-circuit, Raw/normalized
schema validation, Redis caching (hit/miss/unavailable - architecture
review item 4), activity-triggered invalidation (item 14), the
observed_facts/calculated_trends context split (item 3), and the manual
refresh cooldown (item 15).
"""

import json
import uuid

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.exceptions import AIResponseValidationError
from app.core.config import get_settings
from app.repositories import course_repository
from app.schemas.coach import CoachInsightOut, InsufficientDataCoachInsight
from app.services import coach_service
from app.services.learner_model_service import record_answer_learning_event
from tests.ai_fixtures import FakeAIProvider
from tests.practice_fixtures import build_multi_skill_course


class _FakeCoachRedis:
    """Minimal key-value stand-in for redis.Redis - enough of get/setex/
    delete to drive coach_service deterministically, same rationale as
    test_rate_limiting.py's _FakeRedis for check_rate_limit."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.raise_error = False

    def get(self, key: str) -> bytes | None:
        if self.raise_error:
            raise redis.ConnectionError("simulated outage")
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self.raise_error:
            raise redis.ConnectionError("simulated outage")
        self.store[key] = value.encode() if isinstance(value, str) else value

    def delete(self, key: str) -> None:
        if self.raise_error:
            raise redis.ConnectionError("simulated outage")
        self.store.pop(key, None)


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


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _queue_insight(fake_ai_provider: FakeAIProvider, *, summary: str = "Doing well.") -> None:
    fake_ai_provider.next_response = {
        "summary": summary,
        "strengths": ["Consistent effort"],
        "focus_areas": ["SKILL_A"],
        "recommended_action": "Practice SKILL_A a bit more.",
        "data_note": None,
    }


def _seed_one_attempt(db_session: Session, *, user_id: uuid.UUID, is_correct: bool = False):
    fixture = build_multi_skill_course(db_session)
    exercise = course_repository.get_exercise(db_session, fixture.exercise_ids["SKILL_A"][0])
    assert exercise is not None
    record_answer_learning_event(
        db_session, user_id=user_id, exercise=exercise, is_correct=is_correct
    )
    db_session.commit()
    return fixture


# --- Service-level: cache mechanics, via a fake Redis client ---


@pytest.mark.asyncio
async def test_insufficient_data_short_circuits_without_calling_ai(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    build_multi_skill_course(db_session)
    user_id = _signup_and_get_user_id(client)

    result = await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=_FakeCoachRedis()
    )

    assert isinstance(result, InsufficientDataCoachInsight)
    assert fake_ai_provider.calls == []


@pytest.mark.asyncio
async def test_successful_insight_is_generated_and_cached(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    user_id = _signup_and_get_user_id(client)
    _seed_one_attempt(db_session, user_id=user_id)
    _queue_insight(fake_ai_provider, summary="You're making progress.")
    fake_redis = _FakeCoachRedis()

    result = await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=fake_redis
    )

    assert isinstance(result, CoachInsightOut)
    assert result.summary == "You're making progress."
    assert result.from_cache is False
    assert len(fake_ai_provider.calls) == 1
    assert fake_redis.store  # something got cached


@pytest.mark.asyncio
async def test_a_second_request_within_the_ttl_serves_the_cache_not_a_new_ai_call(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    user_id = _signup_and_get_user_id(client)
    _seed_one_attempt(db_session, user_id=user_id)
    _queue_insight(fake_ai_provider)
    fake_redis = _FakeCoachRedis()

    await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=fake_redis
    )
    second = await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=fake_redis
    )

    assert len(fake_ai_provider.calls) == 1  # not called again
    assert isinstance(second, CoachInsightOut)
    assert second.from_cache is True


@pytest.mark.asyncio
async def test_malformed_ai_response_raises_validation_error_and_caches_nothing(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    user_id = _signup_and_get_user_id(client)
    _seed_one_attempt(db_session, user_id=user_id)
    fake_ai_provider.queue_raw_content("not valid json")
    fake_redis = _FakeCoachRedis()

    with pytest.raises(AIResponseValidationError):
        await coach_service.get_coach_insight(
            db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=fake_redis
        )

    assert fake_redis.store == {}


@pytest.mark.asyncio
async def test_redis_being_unreachable_fails_open_not_broken(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    """Mirrors check_rate_limit's existing fail-open contract: a Redis
    outage must never turn into a hard failure over a caching layer."""
    user_id = _signup_and_get_user_id(client)
    _seed_one_attempt(db_session, user_id=user_id)
    _queue_insight(fake_ai_provider)
    fake_redis = _FakeCoachRedis()
    fake_redis.raise_error = True

    result = await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=fake_redis
    )

    assert isinstance(result, CoachInsightOut)
    assert len(fake_ai_provider.calls) == 1


@pytest.mark.asyncio
async def test_invalidate_coach_cache_forces_regeneration_on_the_next_call(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    user_id = _signup_and_get_user_id(client)
    _seed_one_attempt(db_session, user_id=user_id)
    _queue_insight(fake_ai_provider)
    fake_redis = _FakeCoachRedis()

    await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=fake_redis
    )
    coach_service.invalidate_coach_cache(user_id, redis_client=fake_redis)
    assert fake_redis.store == {}

    _queue_insight(fake_ai_provider, summary="Updated after new activity.")
    second = await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=fake_redis
    )

    assert len(fake_ai_provider.calls) == 2  # regenerated, not served stale
    assert isinstance(second, CoachInsightOut)
    assert second.summary == "Updated after new activity."


# --- Context shape: observed_facts / calculated_trends split (item 3) ---


@pytest.mark.asyncio
async def test_context_omits_calculated_trends_when_nothing_qualifies(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    user_id = _signup_and_get_user_id(client)
    _seed_one_attempt(db_session, user_id=user_id)
    _queue_insight(fake_ai_provider)

    await coach_service.get_coach_insight(
        db_session, user_id=user_id, ai_provider=fake_ai_provider, redis_client=_FakeCoachRedis()
    )

    sent_context = json.loads(fake_ai_provider.calls[-1][-1].content)
    assert "weakest_skills" in sent_context["observed_facts"]
    # No improving skills and no repeated mistakes exist yet for a single
    # fresh attempt - the key must be absent entirely, not an empty dict.
    assert "calculated_trends" not in sent_context


# --- HTTP endpoint wiring, real Redis (matching test_rate_limiting.py's
# end-to-end style for anything backed by the real Redis-based rate limiter) ---


def _clear_key(key: str) -> None:
    redis.Redis.from_url(get_settings().redis_url, protocol=2).delete(key)


def test_coach_endpoint_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/me/coach").status_code == 401


def test_coach_endpoint_returns_insufficient_data_message_for_a_fresh_user(
    client: TestClient, db_session: Session
) -> None:
    build_multi_skill_course(db_session)
    token = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "fresh@example.com",
            "password": "correct-horse-battery-staple",
            "native_language": "en",
            "target_language": "es",
            "daily_goal_xp": 50,
        },
    ).json()["access_token"]

    response = client.get("/api/v1/me/coach", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["has_sufficient_data"] is False
    assert body["insight"] is None
    assert body["message"]


def test_coach_endpoint_returns_a_real_insight_for_a_user_with_history(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "history@example.com",
            "password": "correct-horse-battery-staple",
            "native_language": "en",
            "target_language": "es",
            "daily_goal_xp": 50,
        },
    ).json()
    user_id = uuid.UUID(signup["user"]["id"])
    token = signup["access_token"]
    _seed_one_attempt(db_session, user_id=user_id)
    _clear_key(f"coach_insight:{user_id}")
    _queue_insight(fake_ai_provider, summary="Real endpoint insight.")

    response = client.get("/api/v1/me/coach", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["has_sufficient_data"] is True
    assert body["insight"]["summary"] == "Real endpoint insight."


def test_coach_refresh_endpoint_is_rate_limited_to_one_per_cooldown_window(
    client: TestClient, db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "refresh@example.com",
            "password": "correct-horse-battery-staple",
            "native_language": "en",
            "target_language": "es",
            "daily_goal_xp": 50,
        },
    ).json()
    user_id = uuid.UUID(signup["user"]["id"])
    token = signup["access_token"]
    _seed_one_attempt(db_session, user_id=user_id)
    _clear_key(f"coach_insight:{user_id}")
    _clear_key(f"ratelimit:coach-refresh:{user_id}")
    _queue_insight(fake_ai_provider)

    first = client.post("/api/v1/me/coach/refresh", headers=_auth_headers(token))
    _queue_insight(fake_ai_provider)
    second = client.post("/api/v1/me/coach/refresh", headers=_auth_headers(token))

    assert first.status_code == 200
    assert second.status_code == 429

    _clear_key(f"coach_insight:{user_id}")
    _clear_key(f"ratelimit:coach-refresh:{user_id}")
