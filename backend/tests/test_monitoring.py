import pytest

from app.core.config import Settings
from app.core.monitoring import init_error_monitoring


def test_init_error_monitoring_is_a_safe_noop_without_a_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Sentry account exists for this project - the default (empty
    SENTRY_DSN) must never attempt to initialize the SDK or raise."""
    from app.core import monitoring as monitoring_module

    monkeypatch.setattr(monitoring_module, "get_settings", lambda: Settings(sentry_dsn=""))
    init_error_monitoring()  # must not raise
