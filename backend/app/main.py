import logging

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.exceptions import AIProviderError, AIProviderNotConfiguredError
from app.api.v1 import router as api_v1_router
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging_config import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.monitoring import init_error_monitoring
from app.core.rate_limit import check_redis_connectivity

configure_logging()
logger = logging.getLogger("app.main")

# Settings() itself raises (see config.py's _reject_default_secret_in_production)
# if this is a misconfigured production start - fail here, before the app
# object (and any request handling) exists at all.
settings = get_settings()

init_error_monitoring()

app = FastAPI(title="AI Language Learning Tutor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_v1_router)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Starlette's ExceptionMiddleware resolves this handler *before* the
    # exception would otherwise propagate back up through
    # RequestLoggingMiddleware's own try/except - so the full traceback is
    # logged here, not there, or it would never be logged at all. Returns a
    # clean, non-leaking body either way (no debug=True, no raw traceback
    # to the client) with the same request_id RequestLoggingMiddleware
    # attached, so a report from a user can be correlated to server logs.
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "unhandled_exception request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error.", "request_id": request_id},
    )


# Registered once here rather than repeated in every AI-touching route:
# an AI failure must never look like a 500 crash to the client, and must
# never corrupt learning state (the services raise before writing anything).
@app.exception_handler(AIProviderNotConfiguredError)
async def _ai_not_configured_handler(
    request: Request, exc: AIProviderNotConfiguredError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "AI evaluation is not configured on this server."},
    )


@app.exception_handler(AIProviderError)
async def _ai_provider_error_handler(request: Request, exc: AIProviderError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "AI evaluation is temporarily unavailable. Please try again."},
    )


@app.get("/")
def root() -> dict:
    return {"name": "AI Language Learning Tutor API", "status": "running"}


@app.get("/health")
def health(db: Session = Depends(get_db)) -> JSONResponse:
    """Deployment-platform health check (Phase 14): checks the two
    dependencies a request actually needs to succeed - Postgres and Redis -
    rather than just confirming the process is alive. A load balancer/host
    should treat a non-200 here as "don't route traffic to this instance
    yet", not as an application bug to alert on by itself."""
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("health_check_database_failed")
        checks["database"] = "unreachable"

    # Rate limiting itself is designed to fail open when Redis is down (see
    # app/core/rate_limit.py's check_rate_limit), so a Redis outage alone
    # doesn't fail the whole health check the way a database outage does -
    # reported separately so it's visible without blocking traffic over it.
    checks["redis"] = "ok" if check_redis_connectivity() else "unreachable"

    healthy = checks["database"] == "ok"
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
