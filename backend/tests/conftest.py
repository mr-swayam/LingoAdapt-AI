from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.factory import get_ai_provider
from app.api.deps import ai_rate_limit_gate, auth_rate_limit_gate
from app.core.db import Base, get_db
from app.main import app
from tests.ai_fixtures import FakeAIProvider

TEST_DATABASE_URL = "postgresql+psycopg://lingoadapt:lingoadapt@localhost:5432/lingoadapt_dev_test"

_engine = create_engine(TEST_DATABASE_URL)
# join_transaction_mode="create_savepoint": application code under test calls
# session.commit(), which must not end the outer transaction we roll back
# below for isolation. This mode turns those commits into SAVEPOINT
# release/recreate instead of committing the connection's real transaction.
_TestSessionLocal = sessionmaker(
    bind=_engine, autoflush=False, autocommit=False, join_transaction_mode="create_savepoint"
)


@pytest.fixture(scope="session", autouse=True)
def _setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = _engine.connect()
    transaction = connection.begin()
    session = _TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def fake_ai_provider() -> FakeAIProvider:
    return FakeAIProvider()


@pytest.fixture
def client(
    db_session: Session, fake_ai_provider: FakeAIProvider
) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    # Rate limiting (Phase 12) is exercised deliberately in
    # tests/test_rate_limiting.py against a TestClient that does NOT apply
    # this override - bypassed here so the hundreds of unrelated signups/AI
    # calls the rest of the suite makes don't trip real Redis-backed limits.
    app.dependency_overrides[auth_rate_limit_gate] = lambda: None
    app.dependency_overrides[ai_rate_limit_gate] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()
