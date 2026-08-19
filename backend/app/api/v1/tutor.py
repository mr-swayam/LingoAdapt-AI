import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.api.deps import get_current_user, get_metered_ai_provider
from app.core.db import get_db
from app.models.conversation import MessageRole
from app.models.user import User
from app.schemas.conversation import (
    ConversationCorrection,
    ConversationDetailOut,
    ConversationMessageOut,
    ConversationOut,
    CorrectionOut,
    SendMessageRequest,
    SendMessageResponse,
    StartConversationRequest,
    VoiceSendMessageResponse,
)
from app.services import conversation_service, speech_service

router = APIRouter(prefix="/tutor", tags=["tutor"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


def _not_owned() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="This conversation is not yours"
    )


def _build_corrections(corrections: list[ConversationCorrection]) -> list[CorrectionOut]:
    return [
        CorrectionOut(
            original=c.original, corrected=c.corrected, explanation=c.explanation, skill=c.skill
        )
        for c in corrections
    ]


@router.post("/conversations", response_model=ConversationOut)
def start_conversation(
    payload: StartConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    conversation = conversation_service.start_conversation(
        db, user_id=current_user.id, scenario=payload.scenario
    )
    return ConversationOut.from_model(conversation)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ConversationOut]:
    conversations = conversation_service.list_conversations(db, user_id=current_user.id)
    return [ConversationOut.from_model(c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetailOut:
    try:
        conversation = conversation_service.get_conversation(
            db, user_id=current_user.id, conversation_id=conversation_id
        )
    except conversation_service.ConversationNotFoundError as exc:
        raise _not_found() from exc
    except conversation_service.ConversationNotOwnedError as exc:
        raise _not_owned() from exc

    return ConversationDetailOut.from_model_with_messages(conversation)


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> SendMessageResponse:
    try:
        result = await conversation_service.send_message(
            db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            text=payload.text,
            ai_provider=ai_provider,
        )
    except conversation_service.ConversationNotFoundError as exc:
        raise _not_found() from exc
    except conversation_service.ConversationNotOwnedError as exc:
        raise _not_owned() from exc
    except conversation_service.ConversationNotActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This conversation has ended"
        ) from exc

    return SendMessageResponse(
        learner_message=ConversationMessageOut.from_model(result.learner_message),
        tutor_message=ConversationMessageOut.from_model(result.tutor_message),
        corrections=_build_corrections(result.corrections),
    )


@router.post(
    "/conversations/{conversation_id}/voice-messages", response_model=VoiceSendMessageResponse
)
async def send_voice_message(
    conversation_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> VoiceSendMessageResponse:
    """Voice conversation (Phase 8): transcribes the recording, then
    delegates into the exact same conversation_service.send_message flow
    the text endpoint above uses - corrections, learning events, and
    mastery updates all work identically regardless of input channel.

    Ownership is checked *before* transcribing (a real, billed AI call) so
    a request against someone else's conversation fails fast on a cheap
    local lookup rather than paying for a transcription that gets thrown
    away - caught by test_cannot_send_voice_message_to_another_users_-
    conversation initially returning 400 (from the empty-transcript check)
    instead of 403, because transcription ran first.
    """
    try:
        conversation_service.get_conversation(
            db, user_id=current_user.id, conversation_id=conversation_id
        )
    except conversation_service.ConversationNotFoundError as exc:
        raise _not_found() from exc
    except conversation_service.ConversationNotOwnedError as exc:
        raise _not_owned() from exc

    audio_bytes = await file.read()
    try:
        speech_service.validate_audio_size(audio_bytes)
    except speech_service.AudioTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Audio file is too large"
        ) from exc

    transcript = await speech_service.transcribe_audio(
        ai_provider,
        audio_bytes,
        filename=file.filename or "audio.webm",
        content_type=file.content_type or "audio/webm",
    )
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We couldn't hear anything - try recording again.",
        )

    try:
        result = await conversation_service.send_message(
            db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            text=transcript,
            ai_provider=ai_provider,
        )
    except conversation_service.ConversationNotFoundError as exc:
        raise _not_found() from exc
    except conversation_service.ConversationNotOwnedError as exc:
        raise _not_owned() from exc
    except conversation_service.ConversationNotActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This conversation has ended"
        ) from exc

    return VoiceSendMessageResponse(
        learner_message=ConversationMessageOut.from_model(result.learner_message),
        tutor_message=ConversationMessageOut.from_model(result.tutor_message),
        corrections=_build_corrections(result.corrections),
        transcript=transcript,
    )


@router.get("/conversations/{conversation_id}/messages/{message_id}/audio")
async def get_message_audio(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> Response:
    """Audio playback (Phase 8) for any tutor reply, text or voice chat
    alike - synthesized on demand and cached per message id, since a
    message's content never changes once created."""
    try:
        conversation = conversation_service.get_conversation(
            db, user_id=current_user.id, conversation_id=conversation_id
        )
    except conversation_service.ConversationNotFoundError as exc:
        raise _not_found() from exc
    except conversation_service.ConversationNotOwnedError as exc:
        raise _not_owned() from exc

    message = next((m for m in conversation.messages if m.id == message_id), None)
    if message is None or message.role != MessageRole.TUTOR:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message audio not found")

    speech = await speech_service.synthesize_cached(
        ai_provider,
        cache_key=speech_service.message_audio_cache_key(message.id),
        text=message.content,
    )
    return Response(content=speech.audio_bytes, media_type=speech.content_type)


@router.post("/conversations/{conversation_id}/end", response_model=ConversationOut)
def end_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    try:
        conversation = conversation_service.end_conversation(
            db, user_id=current_user.id, conversation_id=conversation_id
        )
    except conversation_service.ConversationNotFoundError as exc:
        raise _not_found() from exc
    except conversation_service.ConversationNotOwnedError as exc:
        raise _not_owned() from exc
    except conversation_service.ConversationNotActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This conversation has already ended"
        ) from exc

    return ConversationOut.from_model(conversation)
