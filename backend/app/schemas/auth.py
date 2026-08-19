import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    native_language: str = Field(min_length=2, max_length=10)
    target_language: str = Field(min_length=2, max_length=10)
    daily_goal_xp: int = Field(default=50, ge=10, le=1000)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    native_language: str
    target_language: str
    daily_goal_xp: int


class PreferencesUpdate(BaseModel):
    native_language: str | None = Field(default=None, min_length=2, max_length=10)
    target_language: str | None = Field(default=None, min_length=2, max_length=10)
    daily_goal_xp: int | None = Field(default=None, ge=10, le=1000)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
    is_admin: bool
    preferences: PreferencesOut


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
