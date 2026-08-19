"""Structured logging setup (Phase 12). Before this, nothing in the app
called logging.config.* anywhere - app.ai's logger.info/warning calls (Groq
latency, transient errors) were emitted into an unconfigured root logger
and went nowhere durable, confirmed during Phase 11's investigation into
what AI-call data already existed. configure_logging() is called once at
import time in main.py, before the FastAPI app is constructed.
"""

import logging.config

from app.core.config import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    settings = get_settings()
    level = "DEBUG" if settings.environment == "development" else "INFO"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": _LOG_FORMAT}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"level": level, "handlers": ["console"]},
            "loggers": {
                # httpx/httpcore's own DEBUG output (every connection/TLS/
                # request-body event) drowned out this app's actual log
                # lines in a real run at DEBUG level - confirmed live while
                # verifying this config against a real Groq call. Neither
                # library logs anything above INFO for normal operation, so
                # WARNING here only suppresses noise, not real problems.
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
            },
        }
    )
