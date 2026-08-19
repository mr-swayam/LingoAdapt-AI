from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.analytics import AiCallLog, AiCallOperation
from tests.test_admin_api import _auth_headers, _signup_admin, _signup_and_get_token


def test_non_admin_cannot_access_analytics(client: TestClient, db_session: Session) -> None:
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/admin/analytics/overview", headers=_auth_headers(token))
    assert response.status_code == 403


def test_unauthenticated_cannot_access_analytics(client: TestClient) -> None:
    response = client.get("/api/v1/admin/analytics/overview")
    assert response.status_code == 401


def test_admin_gets_analytics_overview_shape(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)

    response = client.get("/api/v1/admin/analytics/overview", headers=_auth_headers(token))
    assert response.status_code == 200

    body = response.json()
    for key in (
        "daily_active_users",
        "lesson_completion",
        "practice_completion",
        "day1_retention",
        "day7_retention",
        "ai_stats",
        "top_mistakes",
        "weakest_skills",
        "improvement_trend",
    ):
        assert key in body

    assert body["lesson_completion"] == {
        "started": 0,
        "completed": 0,
        "completion_rate": 0.0,
    }
    assert len(body["daily_active_users"]) == 30
    assert len(body["improvement_trend"]) == 8


def test_analytics_overview_reflects_ai_call_logs(client: TestClient, db_session: Session) -> None:
    token = _signup_admin(client, db_session)

    db_session.add_all(
        [
            AiCallLog(
                operation=AiCallOperation.CHAT,
                provider="groq",
                model="m",
                latency_ms=100,
                success=True,
                created_at=datetime.now(UTC),
            ),
            AiCallLog(
                operation=AiCallOperation.CHAT,
                provider="groq",
                model="m",
                latency_ms=300,
                success=False,
                error_type="AITimeoutError",
                created_at=datetime.now(UTC),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/admin/analytics/overview", headers=_auth_headers(token))
    assert response.status_code == 200
    ai_stats = {row["operation"]: row for row in response.json()["ai_stats"]}

    assert ai_stats["CHAT"]["total_calls"] == 2
    assert ai_stats["CHAT"]["failed_calls"] == 1
    assert ai_stats["CHAT"]["error_rate"] == 0.5
    assert ai_stats["CHAT"]["avg_latency_ms"] == 200.0


def test_analytics_overview_respects_days_query_param(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_admin(client, db_session)

    response = client.get(
        "/api/v1/admin/analytics/overview?days=7", headers=_auth_headers(token)
    )
    assert response.status_code == 200
    assert len(response.json()["daily_active_users"]) == 7
