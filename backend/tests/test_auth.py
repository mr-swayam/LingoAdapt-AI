import pytest
from fastapi.testclient import TestClient

from app.api.v1 import auth as auth_module


def _signup_payload(email: str = "learner@example.com") -> dict:
    return {
        "email": email,
        "password": "correct-horse-battery-staple",
        "native_language": "en",
        "target_language": "es",
        "daily_goal_xp": 50,
    }


def test_signup_creates_user_and_returns_token(client: TestClient) -> None:
    response = client.post("/api/v1/auth/signup", json=_signup_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "learner@example.com"
    assert body["user"]["preferences"] == {
        "native_language": "en",
        "target_language": "es",
        "daily_goal_xp": 50,
    }
    assert "refresh_token" in response.cookies


def test_signup_rejects_duplicate_email(client: TestClient) -> None:
    client.post("/api/v1/auth/signup", json=_signup_payload())
    response = client.post("/api/v1/auth/signup", json=_signup_payload())

    assert response.status_code == 409


def test_signup_rejects_short_password(client: TestClient) -> None:
    payload = _signup_payload()
    payload["password"] = "short"

    response = client.post("/api/v1/auth/signup", json=payload)

    assert response.status_code == 422


def test_login_with_correct_credentials(client: TestClient) -> None:
    client.post("/api/v1/auth/signup", json=_signup_payload())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "learner@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_fails(client: TestClient) -> None:
    client.post("/api/v1/auth/signup", json=_signup_payload())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "learner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_with_unknown_email_fails(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )

    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client: TestClient) -> None:
    signup = client.post("/api/v1/auth/signup", json=_signup_payload())
    access_token = signup.json()["access_token"]

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "learner@example.com"


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_update_preferences(client: TestClient) -> None:
    signup = client.post("/api/v1/auth/signup", json=_signup_payload())
    access_token = signup.json()["access_token"]

    response = client.patch(
        "/api/v1/me/preferences",
        json={"daily_goal_xp": 100},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["daily_goal_xp"] == 100
    assert response.json()["native_language"] == "en"


def test_refresh_issues_new_access_token(client: TestClient) -> None:
    client.post("/api/v1/auth/signup", json=_signup_payload())

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_without_cookie_fails(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    client.post("/api/v1/auth/signup", json=_signup_payload())

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401


def test_refresh_cookie_is_samesite_none_in_production(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real incident (Phase 14): SameSite=Lax cookies are never sent on
    cross-site fetch()/XHR calls, only top-level navigations - invisible in
    local dev (frontend/backend share "localhost", which counts as
    same-site) but breaks session persistence the moment frontend and
    backend are deployed to different domains (Vercel + Railway). Production
    needs SameSite=None (paired with Secure, which browsers require)."""
    monkeypatch.setattr(auth_module.settings, "environment", "production")

    response = client.post("/api/v1/auth/signup", json=_signup_payload("prod-cookie@example.com"))

    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "samesite=none" in set_cookie.lower()
    assert "secure" in set_cookie.lower()


def test_refresh_cookie_is_samesite_lax_in_development(client: TestClient) -> None:
    response = client.post("/api/v1/auth/signup", json=_signup_payload())

    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "samesite=lax" in set_cookie.lower()
