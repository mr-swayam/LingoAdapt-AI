import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class SendFriendRequestIn(BaseModel):
    email: EmailStr


class FriendOut(BaseModel):
    id: uuid.UUID
    email: str


class PendingRequestOut(BaseModel):
    friendship_id: uuid.UUID
    other_user_email: str
    created_at: datetime


class FriendshipOut(BaseModel):
    id: uuid.UUID
    status: str
