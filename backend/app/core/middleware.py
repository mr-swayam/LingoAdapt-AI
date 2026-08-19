import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Every request gets a short id (stored on request.state, returned as
    X-Request-ID, and usable to correlate a client-reported problem with
    server logs) and a completed/failed log line with status and duration.
    This is the app's error-monitoring foundation (Phase 12) - a real
    external service (Sentry or similar) could subscribe to these same log
    lines later, but nothing here invents credentials for a service this
    project doesn't actually have an account with.

    The except-branch below is a defensive fallback, not the primary error
    path: FastAPI's registered `Exception` handler (app/main.py) sits
    *inside* this middleware in Starlette's stack and normally resolves
    unhandled route exceptions into a plain response before they ever
    propagate back up here - that handler does the actual traceback
    logging. This branch only fires for the rarer case of something
    raising outside normal exception-handler resolution."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "request_failed request_id=%s method=%s path=%s duration_ms=%s",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        level = logging.WARNING if response.status_code >= 500 else logging.INFO
        logger.log(
            level,
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
