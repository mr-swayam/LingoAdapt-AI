"""Unit tests for check_rate_limit() (deterministic, fake Redis client - no
network needed), plus true end-to-end tests that the auth/AI dependency
gates actually return 429 once tripped. The end-to-end tests build their
own TestClient WITHOUT tests/conftest.py's blanket
auth_rate_limit_gate/ai_rate_limit_gate override, so they exercise the real
Redis-backed limiter - see conftest.py's `client` fixture for why the rest
of the suite bypasses it.
"""

import redis
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.api.deps import (
    AI_RATE_LIMIT_PER_HOUR,
    AUTH_RATE_LIMIT_PER_MINUTE,
    _get_client_ip,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import check_rate_limit
from app.main import app
from tests.ai_fixtures import FakeAIProvider


def _fake_request(*, headers: dict[str, str], client_host: str | None = "1.2.3.4") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def test_get_client_ip_prefers_x_forwarded_for() -> None:
    """Real bug found in production (Phase 14): request.client.host is the
    reverse proxy's own connecting IP once this app is deployed behind one
    (Railway), not the real client's - a live rate-limit test sent 11
    requests from one machine and never got a 429, because each apparently
    landed with a different request.client.host. X-Forwarded-For is what
    reverse proxies set to the real client IP."""
    request = _fake_request(
        headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1"}, client_host="10.0.0.99"
    )
    assert _get_client_ip(request) == "203.0.113.7"


def test_get_client_ip_falls_back_to_request_client_without_the_header() -> None:
    request = _fake_request(headers={}, client_host="10.0.0.99")
    assert _get_client_ip(request) == "10.0.0.99"


def test_get_client_ip_handles_missing_client_and_header() -> None:
    request = _fake_request(headers={}, client_host=None)
    assert _get_client_ip(request) == "unknown"


class _FakeRedis:
    """Minimal stand-in for redis.Redis - just enough of incr/expire to
    drive check_rate_limit deterministically without a real connection."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.raise_error = False

    def incr(self, key: str) -> int:
        if self.raise_error:
            raise redis.ConnectionError("simulated outage")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, seconds: int) -> None:
        pass


def test_allows_calls_under_the_limit() -> None:
    fake = _FakeRedis()
    for _ in range(3):
        assert check_rate_limit("k", limit=3, window_seconds=60, client=fake) is True


def test_blocks_calls_over_the_limit() -> None:
    fake = _FakeRedis()
    for _ in range(3):
        check_rate_limit("k", limit=3, window_seconds=60, client=fake)
    assert check_rate_limit("k", limit=3, window_seconds=60, client=fake) is False


def test_fails_open_when_redis_is_unreachable() -> None:
    fake = _FakeRedis()
    fake.raise_error = True
    assert check_rate_limit("k", limit=1, window_seconds=60, client=fake) is True


def test_separate_keys_are_independent() -> None:
    fake = _FakeRedis()
    for _ in range(3):
        check_rate_limit("a", limit=3, window_seconds=60, client=fake)
    assert check_rate_limit("b", limit=3, window_seconds=60, client=fake) is True


# --- End-to-end: real Redis, no override ---


def _unmetered_client(db_session: Session, fake_ai_provider: FakeAIProvider) -> TestClient:
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    return TestClient(app)


def _clear_key(key: str) -> None:
    redis.Redis.from_url(get_settings().redis_url, protocol=2).delete(key)


def test_signup_returns_429_once_ip_limit_is_exceeded(
    db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    client = _unmetered_client(db_session, fake_ai_provider)
    try:
        # TestClient requests all share Starlette's fixed "testclient" host,
        # so this key is stable and must be reset before asserting.
        _clear_key("ratelimit:auth:testclient")

        last_status = None
        for i in range(AUTH_RATE_LIMIT_PER_MINUTE + 1):
            response = client.post(
                "/api/v1/auth/signup",
                json={
                    "email": f"ratelimit{i}@example.com",
                    "password": "correct-horse-battery-staple",
                    "native_language": "en",
                    "target_language": "es",
                    "daily_goal_xp": 50,
                },
            )
            last_status = response.status_code

        assert last_status == 429
    finally:
        app.dependency_overrides.clear()
        _clear_key("ratelimit:auth:testclient")


def test_ai_endpoint_returns_429_once_hourly_limit_is_exceeded(
    db_session: Session, fake_ai_provider: FakeAIProvider
) -> None:
    client = _unmetered_client(db_session, fake_ai_provider)
    try:
        signup = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "ai-ratelimit@example.com",
                "password": "correct-horse-battery-staple",
                "native_language": "en",
                "target_language": "es",
                "daily_goal_xp": 50,
            },
        )
        assert signup.status_code == 201
        user_id = signup.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
        _clear_key(f"ratelimit:ai:{user_id}")

        conv = client.post(
            "/api/v1/tutor/conversations", headers=headers, json={"scenario": "RESTAURANT"}
        ).json()

        last_status = None
        for _ in range(AI_RATE_LIMIT_PER_HOUR + 1):
            fake_ai_provider.queue_conversation_turn(reply="hi")
            response = client.post(
                f"/api/v1/tutor/conversations/{conv['id']}/messages",
                headers=headers,
                json={"text": "hello"},
            )
            last_status = response.status_code

        assert last_status == 429
    finally:
        app.dependency_overrides.clear()
