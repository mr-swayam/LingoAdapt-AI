import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.social import (
    FriendOut,
    FriendshipOut,
    PendingRequestOut,
    SendFriendRequestIn,
)
from app.services import friend_service

router = APIRouter(prefix="/friends", tags=["friends"])


def _handle_friend_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, friend_service.UserNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user found with that email"
        )
    if isinstance(exc, friend_service.CannotFriendSelfError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You can't add yourself as a friend"
        )
    if isinstance(exc, friend_service.FriendshipAlreadyExistsError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A friend request already exists between you and this user",
        )
    if isinstance(exc, friend_service.FriendshipNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found"
        )
    if isinstance(exc, friend_service.NotAuthorizedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This friend request is not yours"
        )
    raise exc


@router.get("", response_model=list[FriendOut])
def list_friends(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[FriendOut]:
    friends = friend_service.list_friends(db, current_user.id)
    return [FriendOut(id=f.id, email=f.email) for f in friends]


@router.get("/requests", response_model=dict[str, list[PendingRequestOut]])
def list_pending_requests(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, list[PendingRequestOut]]:
    incoming = friend_service.list_pending_incoming(db, current_user.id)
    outgoing = friend_service.list_pending_outgoing(db, current_user.id)
    return {
        "incoming": [
            PendingRequestOut(
                friendship_id=r.friendship_id,
                other_user_email=r.other_user_email,
                created_at=r.created_at,
            )
            for r in incoming
        ],
        "outgoing": [
            PendingRequestOut(
                friendship_id=r.friendship_id,
                other_user_email=r.other_user_email,
                created_at=r.created_at,
            )
            for r in outgoing
        ],
    }


@router.post("/requests", response_model=FriendshipOut)
def send_friend_request(
    payload: SendFriendRequestIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendshipOut:
    try:
        friendship = friend_service.send_request(
            db, requester_id=current_user.id, addressee_email=payload.email
        )
    except (
        friend_service.UserNotFoundError,
        friend_service.CannotFriendSelfError,
        friend_service.FriendshipAlreadyExistsError,
    ) as exc:
        raise _handle_friend_service_error(exc) from exc

    return FriendshipOut(id=friendship.id, status=friendship.status.value)


@router.post("/requests/{friendship_id}/accept", response_model=FriendshipOut)
def accept_friend_request(
    friendship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendshipOut:
    try:
        friendship = friend_service.accept_request(
            db, user_id=current_user.id, friendship_id=friendship_id
        )
    except (
        friend_service.FriendshipNotFoundError,
        friend_service.NotAuthorizedError,
    ) as exc:
        raise _handle_friend_service_error(exc) from exc

    return FriendshipOut(id=friendship.id, status=friendship.status.value)


@router.delete("/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(
    friendship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        friend_service.remove_or_decline(db, user_id=current_user.id, friendship_id=friendship_id)
    except (
        friend_service.FriendshipNotFoundError,
        friend_service.NotAuthorizedError,
    ) as exc:
        raise _handle_friend_service_error(exc) from exc
