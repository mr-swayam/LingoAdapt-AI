import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories import user_repository

settings = get_settings()


class AuthError(Exception):
    pass


class EmailAlreadyRegisteredError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InvalidRefreshTokenError(AuthError):
    pass


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    user: User


def _issue_tokens(db: Session, user: User) -> IssuedTokens:
    access_token = create_access_token(user.id)
    raw_refresh_token, token_hash = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    user_repository.create_refresh_token(
        db, user_id=user.id, token_hash=token_hash, expires_at=expires_at
    )
    return IssuedTokens(access_token=access_token, refresh_token=raw_refresh_token, user=user)


def signup(
    db: Session,
    *,
    email: str,
    password: str,
    native_language: str,
    target_language: str,
    daily_goal_xp: int,
) -> IssuedTokens:
    if user_repository.get_by_email(db, email) is not None:
        raise EmailAlreadyRegisteredError(email)

    user = user_repository.create_user(
        db,
        email=email,
        hashed_password=hash_password(password),
        native_language=native_language,
        target_language=target_language,
        daily_goal_xp=daily_goal_xp,
    )
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def login(db: Session, *, email: str, password: str) -> IssuedTokens:
    user = user_repository.get_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError(email)

    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def refresh_session(db: Session, *, raw_refresh_token: str) -> IssuedTokens:
    token_hash = hash_refresh_token(raw_refresh_token)
    existing = user_repository.get_refresh_token_by_hash(db, token_hash)

    now = datetime.now(UTC)
    if existing is None or existing.revoked_at is not None or existing.expires_at < now:
        raise InvalidRefreshTokenError

    user_repository.revoke_refresh_token(db, existing)
    user = user_repository.get_by_id(db, existing.user_id)
    if user is None or not user.is_active:
        db.commit()
        raise InvalidRefreshTokenError

    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def logout(db: Session, *, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    existing = user_repository.get_refresh_token_by_hash(db, token_hash)
    if existing is not None and existing.revoked_at is None:
        user_repository.revoke_refresh_token(db, existing)
    db.commit()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return user_repository.get_by_id(db, user_id)
