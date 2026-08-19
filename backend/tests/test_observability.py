import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app
from app.repositories import course_repository


def test_response_includes_a_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_health_endpoint_reports_ok_when_dependencies_are_up(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] in ("ok", "unreachable")  # honest, not fail-open


def test_health_endpoint_reports_503_when_database_is_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app as _app

    def _boom_execute(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated database outage")

    from sqlalchemy.orm import Session

    monkeypatch.setattr(Session, "execute", _boom_execute)

    no_raise_client = TestClient(_app, raise_server_exceptions=False)
    response = no_raise_client.get("/health")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unreachable"


def test_unhandled_exception_returns_clean_500_with_request_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr(course_repository, "list_published_courses", _boom)

    # Starlette's TestClient re-raises server-side exceptions by default
    # (useful for catching bugs in ordinary tests) even though a real
    # client would just receive the JSONResponse my handler built -
    # raise_server_exceptions=False here switches to that real-client view,
    # which is what this test is actually verifying.
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.get("/api/v1/courses")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error."
    assert body["request_id"]
    # Never leak internals - no traceback text, no original exception message.
    assert "simulated unexpected failure" not in response.text
    assert "Traceback" not in response.text


def test_settings_rejects_default_secret_key_in_production() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY must be set"):
        Settings(
            environment="production",
            secret_key="change-me-in-production",
            cors_origins="https://app.example.com",
        )


def test_settings_strips_whitespace_from_string_fields() -> None:
    """Real incident (Phase 14, Railway deploy): a trailing newline ended
    up inside DATABASE_URL's value via the host's environment-variable UI,
    so psycopg tried to connect to a database literally named "railway\\n" -
    which doesn't exist. str_strip_whitespace defends against this for
    every string setting, not just the one that broke."""
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@host:5432/railway\n",
        secret_key="  a-real-random-secret\t",
        cors_origins=" https://app.example.com ",
        environment="development",
    )
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/railway"
    assert settings.secret_key == "a-real-random-secret"
    assert settings.cors_origins == "https://app.example.com"


def test_settings_rejects_localhost_cors_origin_in_production() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS still includes localhost"):
        Settings(
            environment="production",
            secret_key="a-real-random-secret",
            cors_origins="http://localhost:3000",
        )


def test_settings_rejects_localhost_cors_origin_mixed_with_a_real_one() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS still includes localhost"):
        Settings(
            environment="production",
            secret_key="a-real-random-secret",
            cors_origins="https://app.example.com,http://localhost:3000",
        )


def test_settings_allows_a_real_secret_key_and_cors_origin_in_production() -> None:
    Settings(
        environment="production",
        secret_key="a-real-random-secret",
        cors_origins="https://app.example.com",
    )


def test_settings_allows_the_default_secret_key_and_cors_in_development() -> None:
    Settings(environment="development", secret_key="change-me-in-production")
