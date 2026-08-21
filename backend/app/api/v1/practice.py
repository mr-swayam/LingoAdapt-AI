import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.api.deps import get_current_user, get_metered_ai_provider
from app.core.db import get_db
from app.models.user import User
from app.schemas.practice import (
    PracticeAgainRequest,
    PracticeAnswerRequest,
    PracticeAnswerResult,
    PracticeAudioAnswerResult,
    PracticeStartResponse,
)
from app.services import practice_service, speech_service
from app.services.grading import GradingError

router = APIRouter(prefix="/practice", tags=["practice"])


def _handle_practice_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, practice_service.SessionNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Practice session not found"
        )
    if isinstance(exc, practice_service.SessionNotOwnedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This practice session is not yours"
        )
    if isinstance(exc, practice_service.SessionAlreadyCompletedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This practice session is already complete",
        )
    if isinstance(exc, practice_service.QuestionNotInSessionError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This exercise is not part of the given practice session",
        )
    if isinstance(exc, practice_service.NoTargetedExercisesFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching exercises were found to practice",
        )
    if isinstance(exc, practice_service.ExerciseNotOwnedMistakeError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This exercise is not one of your past mistakes",
        )
    raise exc


@router.post("/start", response_model=PracticeStartResponse)
def start_practice(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PracticeStartResponse:
    session, exercises, reasons = practice_service.start_practice_session(
        db, user_id=current_user.id
    )
    return PracticeStartResponse.build(session, exercises, reasons)


@router.post("/practice-again", response_model=PracticeStartResponse)
def practice_again(
    payload: PracticeAgainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeStartResponse:
    """V3.3 Mistake Notebook's "Practice Again" - see practice_service.
    start_targeted_practice_session for the skill_id vs exercise_id
    distinction and the ownership check on exercise_id."""
    skill_ids = [payload.skill_id] if payload.skill_id is not None else None
    exercise_ids = [payload.exercise_id] if payload.exercise_id is not None else None
    try:
        session, exercises, reasons = practice_service.start_targeted_practice_session(
            db, user_id=current_user.id, skill_ids=skill_ids, exercise_ids=exercise_ids
        )
    except (
        practice_service.NoTargetedExercisesFoundError,
        practice_service.ExerciseNotOwnedMistakeError,
    ) as exc:
        raise _handle_practice_service_error(exc) from exc
    return PracticeStartResponse.build(session, exercises, reasons)


@router.post("/{session_id}/answer", response_model=PracticeAnswerResult)
async def answer_practice_question(
    session_id: uuid.UUID,
    payload: PracticeAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> PracticeAnswerResult:
    try:
        result = await practice_service.submit_practice_answer(
            db,
            user_id=current_user.id,
            session_id=session_id,
            exercise_id=payload.exercise_id,
            submitted_answer=payload.submitted_answer,
            ai_provider=ai_provider,
        )
    except (
        practice_service.SessionNotFoundError,
        practice_service.SessionNotOwnedError,
        practice_service.SessionAlreadyCompletedError,
        practice_service.QuestionNotInSessionError,
    ) as exc:
        raise _handle_practice_service_error(exc) from exc
    except GradingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PracticeAnswerResult(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        explanation=result.explanation,
        session_completed=result.session_completed,
        correct_count=result.correct_count,
        total_count=result.total_count,
    )


@router.post("/{session_id}/answer-audio", response_model=PracticeAudioAnswerResult)
async def answer_practice_question_audio(
    session_id: uuid.UUID,
    exercise_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> PracticeAudioAnswerResult:
    try:
        existing = practice_service.get_existing_answer(
            db, user_id=current_user.id, session_id=session_id, exercise_id=exercise_id
        )
    except (practice_service.SessionNotFoundError, practice_service.SessionNotOwnedError) as exc:
        raise _handle_practice_service_error(exc) from exc

    if existing is not None:
        # Already answered - reuse the original transcript rather than
        # paying for (and discarding) a second real STT call.
        transcript = (existing.submitted_answer or {}).get("text", "")
    else:
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

    try:
        result = await practice_service.submit_practice_answer(
            db,
            user_id=current_user.id,
            session_id=session_id,
            exercise_id=exercise_id,
            submitted_answer={"text": transcript},
            ai_provider=ai_provider,
        )
    except (
        practice_service.SessionNotFoundError,
        practice_service.SessionNotOwnedError,
        practice_service.SessionAlreadyCompletedError,
        practice_service.QuestionNotInSessionError,
    ) as exc:
        raise _handle_practice_service_error(exc) from exc
    except GradingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PracticeAudioAnswerResult(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        explanation=result.explanation,
        session_completed=result.session_completed,
        correct_count=result.correct_count,
        total_count=result.total_count,
        transcript=transcript,
    )
