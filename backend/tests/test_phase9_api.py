from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def test_quests_endpoint_returns_the_three_templates(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/me/quests", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert {q["quest_type"] for q in body} == {
        "EARN_XP",
        "COMPLETE_LESSON",
        "PRACTICE_SESSION",
    }
    assert all(q["completed"] is False for q in body)


def test_quests_endpoint_is_idempotent_across_calls(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_and_get_token(client)
    first = client.get("/api/v1/me/quests", headers=_auth_headers(token)).json()
    second = client.get("/api/v1/me/quests", headers=_auth_headers(token)).json()
    assert {q["id"] for q in first} == {q["id"] for q in second}


def test_quests_require_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me/quests")
    assert response.status_code == 401


def test_leaderboard_endpoint_returns_own_tier_and_self_entry(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/leaderboard", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "SPARK"
    assert len(body["entries"]) == 1
    assert body["entries"][0]["is_me"] is True
    assert body["entries"][0]["email"] == "learner@example.com"


def test_progress_endpoint_includes_gem_balance_and_league_tier(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/me/progress", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["gem_balance"] == 0
    assert body["league_tier"] == "SPARK"


def test_friend_request_flow_end_to_end(client: TestClient, db_session: Session) -> None:
    seed_achievement_catalog(db_session)
    token_a = _signup_and_get_token(client, email="a@example.com")
    token_b = _signup_and_get_token(client, email="b@example.com")

    sent = client.post(
        "/api/v1/friends/requests",
        headers=_auth_headers(token_a),
        json={"email": "b@example.com"},
    )
    assert sent.status_code == 200
    friendship_id = sent.json()["id"]
    assert sent.json()["status"] == "PENDING"

    incoming_for_b = client.get(
        "/api/v1/friends/requests", headers=_auth_headers(token_b)
    ).json()
    assert len(incoming_for_b["incoming"]) == 1
    assert incoming_for_b["incoming"][0]["other_user_email"] == "a@example.com"

    accepted = client.post(
        f"/api/v1/friends/requests/{friendship_id}/accept", headers=_auth_headers(token_b)
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"

    friends_of_a = client.get("/api/v1/friends", headers=_auth_headers(token_a)).json()
    assert friends_of_a == [{"id": friends_of_a[0]["id"], "email": "b@example.com"}]

    achievements_a = client.get("/api/v1/achievements", headers=_auth_headers(token_a)).json()
    first_friend = next(a for a in achievements_a if a["code"] == "FIRST_FRIEND")
    assert first_friend["earned"] is True


def test_cannot_friend_request_a_nonexistent_email(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/friends/requests",
        headers=_auth_headers(token),
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 404


def test_cannot_accept_someone_elses_friend_request(
    client: TestClient, db_session: Session
) -> None:
    token_a = _signup_and_get_token(client, email="a@example.com")
    _signup_and_get_token(client, email="b@example.com")
    token_c = _signup_and_get_token(client, email="c@example.com")

    sent = client.post(
        "/api/v1/friends/requests",
        headers=_auth_headers(token_a),
        json={"email": "b@example.com"},
    )
    friendship_id = sent.json()["id"]

    response = client.post(
        f"/api/v1/friends/requests/{friendship_id}/accept", headers=_auth_headers(token_c)
    )
    assert response.status_code == 403


def test_remove_friendship_lets_a_new_request_be_sent(
    client: TestClient, db_session: Session
) -> None:
    token_a = _signup_and_get_token(client, email="a@example.com")
    _signup_and_get_token(client, email="b@example.com")

    sent = client.post(
        "/api/v1/friends/requests",
        headers=_auth_headers(token_a),
        json={"email": "b@example.com"},
    )
    friendship_id = sent.json()["id"]

    delete_response = client.delete(
        f"/api/v1/friends/{friendship_id}", headers=_auth_headers(token_a)
    )
    assert delete_response.status_code == 204

    resent = client.post(
        "/api/v1/friends/requests",
        headers=_auth_headers(token_a),
        json={"email": "b@example.com"},
    )
    assert resent.status_code == 200


def test_friends_leaderboard_starts_empty_except_self(
    client: TestClient, db_session: Session
) -> None:
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/leaderboard/friends", headers=_auth_headers(token))
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["is_me"] is True
