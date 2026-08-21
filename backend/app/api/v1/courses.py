import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import course_repository, gamification_repository
from app.schemas.course import CourseDetailOut, CourseSummaryOut

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseSummaryOut])
def list_courses(db: Session = Depends(get_db)) -> list[CourseSummaryOut]:
    courses = course_repository.list_published_courses(db)
    return [CourseSummaryOut.from_model(c) for c in courses]


@router.get("/{course_id}", response_model=CourseDetailOut)
def get_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseDetailOut:
    """Authenticated (V2 redesign) so the real per-lesson completion state
    can be attached for the /learn path visual - course content itself
    isn't secret, but which lessons *this* learner has finished is."""
    course = course_repository.get_course_detail(db, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    lesson_ids = [lesson.id for unit in course.units for lesson in unit.lessons]
    completed_lesson_ids = frozenset(
        gamification_repository.get_completed_lesson_ids(db, current_user.id, lesson_ids)
    )
    return CourseDetailOut.from_model(course, completed_lesson_ids=completed_lesson_ids)
