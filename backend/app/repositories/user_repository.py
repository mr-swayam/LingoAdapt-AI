import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import RefreshToken, User, UserPreferences


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def create_user(
    db: Session,
    *,
    email: str,
    hashed_password: str,
    native_language: str,
    target_language: str,
    daily_goal_xp: int,
) -> User:
    user = User(email=email, hashed_password=hashed_password)
    user.preferences = UserPreferences(
        native_language=native_language,
        target_language=target_language,
        daily_goal_xp=daily_goal_xp,
    )
    db.add(user)
    db.flush()
    return user


def update_preferences(
    db: Session,
    user: User,
    *,
    native_language: str | None,
    target_language: str | None,
    daily_goal_xp: int | None,
) -> UserPreferences:
    prefs = user.preferences
    if native_language is not None:
        prefs.native_language = native_language
    if target_language is not None:
        prefs.target_language = target_language
    if daily_goal_xp is not None:
        prefs.daily_goal_xp = daily_goal_xp
    db.flush()
    return prefs


def create_refresh_token(
    db: Session, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> RefreshToken:
    token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(token)
    db.flush()
    return token


def get_refresh_token_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    return db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()


def revoke_refresh_token(db: Session, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(UTC)
    db.flush()
