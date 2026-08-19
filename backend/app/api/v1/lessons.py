import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import course_repository
from app.schemas.course import LessonStartResponse, LessonSummaryOut
from app.services import lesson_service

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("/{lesson_id}", response_model=LessonSummaryOut)
def get_lesson(lesson_id: uuid.UUID, db: Session = Depends(get_db)) -> LessonSummaryOut:
    lesson = course_repository.get_lesson(db, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return LessonSummaryOut.from_model(lesson)


@router.post("/{lesson_id}/start", response_model=LessonStartResponse)
def start_lesson(
    lesson_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LessonStartResponse:
    try:
        attempt, lesson = lesson_service.start_lesson(
            db, user_id=current_user.id, lesson_id=lesson_id
        )
    except lesson_service.LessonNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
        ) from exc

    return LessonStartResponse.build(attempt, lesson)
