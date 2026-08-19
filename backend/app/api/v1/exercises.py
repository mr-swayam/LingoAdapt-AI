import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.api.deps import get_current_user, get_metered_ai_provider
from app.core.db import get_db
from app.models.course import ExerciseType
from app.models.user import User
from app.repositories import course_repository
from app.schemas.course import AnswerResultOut, AnswerSubmitRequest, AudioAnswerResultOut
from app.services import lesson_service, speech_service
from app.services.grading import GradingError

router = APIRouter(prefix="/exercises", tags=["exercises"])


def _handle_lesson_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, lesson_service.AttemptNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson attempt not found"
        )
    if isinstance(exc, lesson_service.AttemptNotOwnedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This lesson attempt is not yours"
        )
    if isinstance(exc, lesson_service.AttemptAlreadyCompletedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This lesson attempt is already complete"
        )
    if isinstance(exc, lesson_service.ExerciseNotInAttemptError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This exercise does not belong to the given lesson attempt",
        )
    raise exc


@router.post("/{exercise_id}/answer", response_model=AnswerResultOut)
async def answer_exercise(
    exercise_id: uuid.UUID,
    payload: AnswerSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> AnswerResultOut:
    try:
        result = await lesson_service.submit_answer(
            db,
            user_id=current_user.id,
            exercise_id=exercise_id,
            lesson_attempt_id=payload.lesson_attempt_id,
            submitted_answer=payload.submitted_answer,
            ai_provider=ai_provider,
        )
    except (
        lesson_service.AttemptNotFoundError,
        lesson_service.AttemptNotOwnedError,
        lesson_service.AttemptAlreadyCompletedError,
        lesson_service.ExerciseNotInAttemptError,
    ) as exc:
        raise _handle_lesson_service_error(exc) from exc
    except GradingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AnswerResultOut(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        explanation=result.explanation,
        lesson_completed=result.lesson_completed,
        correct_count=result.correct_count,
        total_count=result.total_count,
        xp_earned=result.xp_earned,
        current_streak=result.current_streak,
        new_achievements=result.new_achievement_codes,
    )


@router.post("/{exercise_id}/answer-audio", response_model=AudioAnswerResultOut)
async def answer_exercise_audio(
    exercise_id: uuid.UUID,
    lesson_attempt_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> AudioAnswerResultOut:
    """SPEAKING exercises: the learner records themselves instead of typing.
    Transcribes once at this boundary, then delegates into the exact same
    lesson_service.submit_answer/grade_exercise path a typed answer would
    take - grading itself never touches audio (app/services/grading.py's
    _grade_speaking just compares text)."""
    try:
        existing = lesson_service.get_existing_answer(
            db,
            user_id=current_user.id,
            exercise_id=exercise_id,
            lesson_attempt_id=lesson_attempt_id,
        )
    except (lesson_service.AttemptNotFoundError, lesson_service.AttemptNotOwnedError) as exc:
        raise _handle_lesson_service_error(exc) from exc

    if existing is not None:
        # Already answered in this attempt - reuse the original transcript
        # rather than paying for (and then discarding) a second real STT
        # call, exactly the resubmission concern ai_grading.py's docstring
        # already documents for SHORT_ANSWER.
        transcript = existing.submitted_answer.get("text", "")
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
        result = await lesson_service.submit_answer(
            db,
            user_id=current_user.id,
            exercise_id=exercise_id,
            lesson_attempt_id=lesson_attempt_id,
            submitted_answer={"text": transcript},
            ai_provider=ai_provider,
        )
    except (
        lesson_service.AttemptNotFoundError,
        lesson_service.AttemptNotOwnedError,
        lesson_service.AttemptAlreadyCompletedError,
        lesson_service.ExerciseNotInAttemptError,
    ) as exc:
        raise _handle_lesson_service_error(exc) from exc
    except GradingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AudioAnswerResultOut(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        explanation=result.explanation,
        lesson_completed=result.lesson_completed,
        correct_count=result.correct_count,
        total_count=result.total_count,
        xp_earned=result.xp_earned,
        current_streak=result.current_streak,
        new_achievements=result.new_achievement_codes,
        transcript=transcript,
    )


@router.get("/{exercise_id}/audio")
async def get_exercise_audio(
    exercise_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider | None = Depends(get_metered_ai_provider),
) -> Response:
    """LISTENING exercises: synthesizes (and caches) the exercise's hidden
    text_to_speak - kept in correct_answer, never in payload, so it never
    leaks to the client as text (same principle as SHORT_ANSWER hiding its
    model_answer/rubric)."""
    exercise = course_repository.get_exercise(db, exercise_id)
    if exercise is None or exercise.type != ExerciseType.LISTENING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listening exercise not found"
        )

    text_to_speak = exercise.correct_answer.get("text_to_speak", "")
    voice = exercise.correct_answer.get("voice", speech_service.DEFAULT_VOICE)
    speech = await speech_service.synthesize_cached(
        ai_provider,
        cache_key=speech_service.exercise_audio_cache_key(exercise.id),
        text=text_to_speak,
        voice=voice,
    )
    return Response(content=speech.audio_bytes, media_type=speech.content_type)
