"""Creates a user directly via the repository (no HTTP signup round-trip) -
for tests that need a handful of users to interact with each other (leagues,
friends) and don't care about the auth flow itself."""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.repositories import user_repository


def create_user(
    db: Session,
    *,
    email: str,
    native_language: str = "en",
    target_language: str = "es",
    daily_goal_xp: int = 50,
    is_admin: bool = False,
) -> User:
    user = user_repository.create_user(
        db,
        email=email,
        hashed_password=hash_password("correct-horse-battery-staple"),
        native_language=native_language,
        target_language=target_language,
        daily_goal_xp=daily_goal_xp,
    )
    user.is_admin = is_admin
    db.commit()
    return user
