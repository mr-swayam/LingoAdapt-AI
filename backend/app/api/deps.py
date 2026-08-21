import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.factory import get_ai_provider
from app.ai.metering import MeteredAIProvider
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import check_rate_limit
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories import user_repository

# Auth endpoints are unauthenticated by nature, so they can only be
# rate-limited by IP - generous enough for a shared office/NAT IP's normal
# traffic, tight enough to blunt credential-stuffing / signup-spam scripts.
AUTH_RATE_LIMIT_PER_MINUTE = 10
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60

# AI calls are the one real per-request dollar cost in this app (rules.md
# §2.6/§13 - AI cost controls). Per-user, generous enough for normal lesson
# + tutor use in an hour, tight enough to bound a single account's worst-case
# spend if a client bug (or abuse) started hammering an AI endpoint.
AI_RATE_LIMIT_PER_HOUR = 30
AI_RATE_LIMIT_WINDOW_SECONDS = 3600

# V3.1 AI Coach manual "Refresh" - a second, tighter, feature-specific limit
# on top of (not instead of) AI_RATE_LIMIT_PER_HOUR above (V3 architecture
# review item 15). GET /me/coach itself is unmetered (cache hits and the
# insufficient-data short-circuit cost nothing) - only an explicit refresh,
# which always bypasses the cache, is gated here.
COACH_REFRESH_LIMIT = 1
COACH_REFRESH_WINDOW_SECONDS = 300

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _CREDENTIALS_ERROR

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _CREDENTIALS_ERROR

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise _CREDENTIALS_ERROR from exc

    user = user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR

    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


def _get_client_ip(request: Request) -> str:
    # Real bug found in production (Phase 14, Railway): request.client.host
    # is the *proxy's* connecting IP, not the real client's, once this app
    # sits behind any reverse proxy/load balancer - a live rate-limit test
    # sent 11 requests from one machine and never got a 429, because each
    # one apparently landed with a different request.client.host. Trusting
    # the first hop of X-Forwarded-For is standard practice specifically
    # for this deployment shape (this app is never exposed directly to the
    # internet - Railway's edge always sets/overwrites this header, so a
    # client can't spoof their way around the limit by forging it).
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def auth_rate_limit_gate(request: Request) -> None:
    """Applied to /auth/signup and /auth/login. A separate, overridable
    dependency (rather than inlined in the route) so tests can bypass it in
    bulk the same way they swap in FakeAIProvider - see tests/conftest.py -
    while tests/test_rate_limiting.py exercises the real thing."""
    client_ip = _get_client_ip(request)
    allowed = check_rate_limit(
        f"ratelimit:auth:{client_ip}",
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
        window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again in a minute.",
        )


def ai_rate_limit_gate(current_user: User = Depends(get_current_user)) -> None:
    """Applied inside get_metered_ai_provider below, so every AI-touching
    route is covered automatically without each router remembering to add
    it separately."""
    allowed = check_rate_limit(
        f"ratelimit:ai:{current_user.id}",
        limit=AI_RATE_LIMIT_PER_HOUR,
        window_seconds=AI_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI usage limit reached for this hour. Please try again later.",
        )


def coach_refresh_rate_limit_gate(current_user: User = Depends(get_current_user)) -> None:
    """Applied only to the explicit Coach "Refresh" action - a normal
    GET /me/coach is not gated by this at all (cache hits/insufficient-data
    responses cost nothing to serve)."""
    allowed = check_rate_limit(
        f"ratelimit:coach-refresh:{current_user.id}",
        limit=COACH_REFRESH_LIMIT,
        window_seconds=COACH_REFRESH_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait a few minutes before refreshing your coach insight again.",
        )


def get_metered_ai_provider(
    ai_provider: AIProvider | None = Depends(get_ai_provider),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(ai_rate_limit_gate),
) -> AIProvider | None:
    """Wraps get_ai_provider()'s singleton with a request-scoped provider
    that logs every call's latency/success to ai_call_logs (Phase 11) -
    swapped in wherever `Depends(get_ai_provider)` is used by an
    authenticated endpoint, so AI metrics collection stays outside every
    feature's own business logic. Gated by ai_rate_limit_gate first, so a
    caller past their hourly limit never reaches (and never pays for) the
    provider at all."""
    if ai_provider is None:
        return None
    return MeteredAIProvider(
        ai_provider,
        db=db,
        user_id=current_user.id,
        provider_name=get_settings().ai_provider,
    )
