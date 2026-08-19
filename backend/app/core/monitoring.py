"""Optional production error monitoring (Phase 14). A no-op unless
SENTRY_DSN is set - this project has no Sentry account of its own to wire
up for real (rules.md: never invent credentials for a service that
doesn't exist), so this is the ready-to-flip switch that Phase 12's
structured logging + request-ID correlation (app/core/middleware.py) was
already built as the foundation for. Once a real DSN exists, setting the
env var is the only step required - no code change.
"""

import logging

from app.core.config import get_settings

logger = logging.getLogger("app.monitoring")


def init_error_monitoring() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        logger.info("error_monitoring_disabled reason=no_sentry_dsn_configured")
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        # Conservative default for a small beta - full request tracing on
        # every request is unnecessary volume/cost for 5-20 users; this
        # only affects performance tracing, not error capture (errors are
        # always captured regardless of this rate).
        traces_sample_rate=0.1,
    )
    logger.info("error_monitoring_initialized environment=%s", settings.environment)
