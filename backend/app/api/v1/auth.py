from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import auth_rate_limit_gate
from app.core.config import get_settings
from app.core.db import get_db
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_PATH = "/api/v1/auth"

_INVALID_REFRESH_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
)


def _set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    # SameSite=Lax cookies are never sent on cross-site fetch()/XHR calls -
    # only on top-level navigations. That's invisible in local dev (frontend
    # and backend are different ports of the same "localhost" site, which
    # counts as same-site), but breaks silently the moment frontend and
    # backend are deployed to different domains (Vercel + Railway, a real
    # Phase 14 production deploy) - login succeeds, but every subsequent
    # page's silent refresh-token call carries no cookie, so the session
    # never survives a fresh page load. SameSite=None (which browsers
    # require pairing with Secure) is what actually works cross-site;
    # Lax is kept for local development since it doesn't need cross-site
    # cookies and staying stricter there is free security margin.
    is_production_like = settings.environment != "development"
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=is_production_like,
        samesite="none" if is_production_like else "lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path=_REFRESH_COOKIE_PATH)


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit_gate)],
)
def signup(
    payload: SignupRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    try:
        tokens = auth_service.signup(
            db,
            email=payload.email,
            password=payload.password,
            native_language=payload.native_language,
            target_language=payload.target_language,
            daily_goal_xp=payload.daily_goal_xp,
        )
    except auth_service.EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc

    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token, user=tokens.user)  # type: ignore[arg-type]


@router.post(
    "/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit_gate)]
)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    try:
        tokens = auth_service.login(db, email=payload.email, password=payload.password)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        ) from exc

    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token, user=tokens.user)  # type: ignore[arg-type]


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
) -> TokenResponse:
    if refresh_token is None:
        raise _INVALID_REFRESH_TOKEN

    try:
        tokens = auth_service.refresh_session(db, raw_refresh_token=refresh_token)
    except auth_service.InvalidRefreshTokenError as exc:
        _clear_refresh_cookie(response)
        raise _INVALID_REFRESH_TOKEN from exc

    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token, user=tokens.user)  # type: ignore[arg-type]


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
) -> None:
    if refresh_token is not None:
        auth_service.logout(db, raw_refresh_token=refresh_token)
    _clear_refresh_cookie(response)
