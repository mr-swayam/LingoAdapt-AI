from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


# The real /health check (Phase 14 - checks Postgres/Redis connectivity,
# not just that the process is alive) lives in tests/test_observability.py,
# next to the request-ID/error-monitoring tests it was built alongside.
