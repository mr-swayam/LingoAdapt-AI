import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories import course_repository
from app.schemas.course import CourseDetailOut, CourseSummaryOut

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseSummaryOut])
def list_courses(db: Session = Depends(get_db)) -> list[CourseSummaryOut]:
    courses = course_repository.list_published_courses(db)
    return [CourseSummaryOut.from_model(c) for c in courses]


@router.get("/{course_id}", response_model=CourseDetailOut)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseDetailOut:
    course = course_repository.get_course_detail(db, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return CourseDetailOut.from_model(course)
