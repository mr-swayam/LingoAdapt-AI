import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.core.db import get_db
from app.schemas.admin import (
    CourseAdminDetailOut,
    CourseAdminOut,
    CourseCreateIn,
    CourseUpdateIn,
    ExerciseAdminOut,
    ExerciseCreateIn,
    ExerciseUpdateIn,
    LanguageIn,
    LanguageOut,
    LessonAdminDetailOut,
    LessonCreateIn,
    LessonOut,
    LessonUpdateIn,
    SkillCreateIn,
    SkillOut,
    SkillUpdateIn,
    UnitCreateIn,
    UnitOut,
    UnitUpdateIn,
    ValidationResultOut,
)
from app.schemas.analytics import AnalyticsOverviewOut
from app.services import admin_content_service as svc
from app.services import analytics_service
from app.services.content_validation import validate_course_for_publish

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin_user)])


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _handle_admin_error(exc: Exception) -> HTTPException:
    if isinstance(exc, svc.CourseNotFoundError):
        return _not_found("Course not found")
    if isinstance(exc, svc.UnitNotFoundError):
        return _not_found("Unit not found")
    if isinstance(exc, svc.LessonNotFoundError):
        return _not_found("Lesson not found")
    if isinstance(exc, svc.SkillNotFoundError):
        return _not_found("Skill not found")
    if isinstance(exc, svc.ExerciseNotFoundError):
        return _not_found("Exercise not found")
    if isinstance(exc, svc.LanguageNotFoundError):
        return _not_found("Language not found")
    if isinstance(exc, svc.DuplicateLanguageCodeError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A language with that code already exists"
        )
    if isinstance(exc, svc.DuplicateSkillCodeError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A skill with that code already exists in this course",
        )
    raise exc


# --- Languages ---


@router.get("/languages", response_model=list[LanguageOut])
def list_languages(db: Session = Depends(get_db)) -> list[LanguageOut]:
    return [LanguageOut.model_validate(x) for x in svc.list_languages(db)]


@router.post("/languages", response_model=LanguageOut)
def create_language(payload: LanguageIn, db: Session = Depends(get_db)) -> LanguageOut:
    try:
        language = svc.create_language(db, code=payload.code, name=payload.name)
    except svc.DuplicateLanguageCodeError as exc:
        raise _handle_admin_error(exc) from exc
    return LanguageOut.model_validate(language)


# --- Courses ---


@router.get("/courses", response_model=list[CourseAdminOut])
def list_courses(db: Session = Depends(get_db)) -> list[CourseAdminOut]:
    return [CourseAdminOut.from_model(c) for c in svc.list_courses(db)]


@router.post("/courses", response_model=CourseAdminOut)
def create_course(payload: CourseCreateIn, db: Session = Depends(get_db)) -> CourseAdminOut:
    course = svc.create_course(
        db, language_id=payload.language_id, title=payload.title, description=payload.description
    )
    return CourseAdminOut.from_model(svc.get_course(db, course.id))


@router.get("/courses/{course_id}", response_model=CourseAdminDetailOut)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseAdminDetailOut:
    try:
        course = svc.get_course(db, course_id)
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return CourseAdminDetailOut.from_model(course)


@router.patch("/courses/{course_id}", response_model=CourseAdminOut)
def update_course(
    course_id: uuid.UUID, payload: CourseUpdateIn, db: Session = Depends(get_db)
) -> CourseAdminOut:
    try:
        svc.update_course(db, course_id, title=payload.title, description=payload.description)
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return CourseAdminOut.from_model(svc.get_course(db, course_id))


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    try:
        svc.delete_course(db, course_id)
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc


@router.get("/courses/{course_id}/validate", response_model=ValidationResultOut)
def validate_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> ValidationResultOut:
    try:
        course = svc.get_course(db, course_id)
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    errors = validate_course_for_publish(course)
    return ValidationResultOut(valid=not errors, errors=errors)


@router.post("/courses/{course_id}/publish", response_model=CourseAdminOut)
def publish_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseAdminOut:
    try:
        course = svc.publish_course(db, course_id)
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    except svc.CourseNotPublishableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Course is not ready to publish", "errors": exc.errors},
        ) from exc
    return CourseAdminOut.from_model(course)


@router.post("/courses/{course_id}/unpublish", response_model=CourseAdminOut)
def unpublish_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseAdminOut:
    try:
        course = svc.unpublish_course(db, course_id)
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return CourseAdminOut.from_model(course)


# --- Skills ---


@router.get("/courses/{course_id}/skills", response_model=list[SkillOut])
def list_skills(course_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SkillOut]:
    try:
        skills = svc.list_skills_for_course(db, course_id)
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return [SkillOut.model_validate(s) for s in skills]


@router.post("/skills", response_model=SkillOut)
def create_skill(payload: SkillCreateIn, db: Session = Depends(get_db)) -> SkillOut:
    try:
        skill = svc.create_skill(
            db, course_id=payload.course_id, code=payload.code, name=payload.name
        )
    except (svc.CourseNotFoundError, svc.DuplicateSkillCodeError) as exc:
        raise _handle_admin_error(exc) from exc
    return SkillOut.model_validate(skill)


@router.patch("/skills/{skill_id}", response_model=SkillOut)
def update_skill(
    skill_id: uuid.UUID, payload: SkillUpdateIn, db: Session = Depends(get_db)
) -> SkillOut:
    try:
        skill = svc.update_skill(db, skill_id, name=payload.name)
    except svc.SkillNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return SkillOut.model_validate(skill)


# --- Units ---


@router.post("/units", response_model=UnitOut)
def create_unit(payload: UnitCreateIn, db: Session = Depends(get_db)) -> UnitOut:
    try:
        unit = svc.create_unit(
            db, course_id=payload.course_id, title=payload.title, position=payload.position
        )
    except svc.CourseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return UnitOut.model_validate(unit)


@router.patch("/units/{unit_id}", response_model=UnitOut)
def update_unit(
    unit_id: uuid.UUID, payload: UnitUpdateIn, db: Session = Depends(get_db)
) -> UnitOut:
    try:
        unit = svc.update_unit(db, unit_id, title=payload.title, position=payload.position)
    except svc.UnitNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return UnitOut.model_validate(unit)


@router.delete("/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    try:
        svc.delete_unit(db, unit_id)
    except svc.UnitNotFoundError as exc:
        raise _handle_admin_error(exc) from exc


# --- Lessons ---


@router.post("/lessons", response_model=LessonOut)
def create_lesson(payload: LessonCreateIn, db: Session = Depends(get_db)) -> LessonOut:
    try:
        lesson = svc.create_lesson(
            db, unit_id=payload.unit_id, title=payload.title, position=payload.position
        )
    except svc.UnitNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return LessonOut.model_validate(lesson)


@router.get("/lessons/{lesson_id}", response_model=LessonAdminDetailOut)
def get_lesson(lesson_id: uuid.UUID, db: Session = Depends(get_db)) -> LessonAdminDetailOut:
    try:
        lesson = svc.get_lesson(db, lesson_id)
    except svc.LessonNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return LessonAdminDetailOut.from_model(lesson)


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
def update_lesson(
    lesson_id: uuid.UUID, payload: LessonUpdateIn, db: Session = Depends(get_db)
) -> LessonOut:
    try:
        lesson = svc.update_lesson(db, lesson_id, title=payload.title, position=payload.position)
    except svc.LessonNotFoundError as exc:
        raise _handle_admin_error(exc) from exc
    return LessonOut.model_validate(lesson)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(lesson_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    try:
        svc.delete_lesson(db, lesson_id)
    except svc.LessonNotFoundError as exc:
        raise _handle_admin_error(exc) from exc


# --- Exercises ---


@router.post("/exercises", response_model=ExerciseAdminOut)
def create_exercise(payload: ExerciseCreateIn, db: Session = Depends(get_db)) -> ExerciseAdminOut:
    try:
        exercise = svc.create_exercise(
            db,
            lesson_id=payload.lesson_id,
            skill_id=payload.skill_id,
            type=payload.type,
            prompt=payload.prompt,
            payload=payload.payload,
            correct_answer=payload.correct_answer,
            explanation=payload.explanation,
            difficulty=payload.difficulty,
            position=payload.position,
            options=[o.model_dump() for o in payload.options],
        )
    except (svc.LessonNotFoundError, svc.SkillNotFoundError) as exc:
        raise _handle_admin_error(exc) from exc
    return ExerciseAdminOut.from_model(exercise)


@router.patch("/exercises/{exercise_id}", response_model=ExerciseAdminOut)
def update_exercise(
    exercise_id: uuid.UUID, payload: ExerciseUpdateIn, db: Session = Depends(get_db)
) -> ExerciseAdminOut:
    options = (
        [o.model_dump() for o in payload.options] if payload.options is not None else None
    )
    try:
        exercise = svc.update_exercise(
            db,
            exercise_id,
            skill_id=payload.skill_id,
            prompt=payload.prompt,
            payload=payload.payload,
            correct_answer=payload.correct_answer,
            explanation=payload.explanation,
            explanation_set=payload.explanation_set,
            difficulty=payload.difficulty,
            position=payload.position,
            options=options,
        )
    except (svc.ExerciseNotFoundError, svc.SkillNotFoundError) as exc:
        raise _handle_admin_error(exc) from exc
    return ExerciseAdminOut.from_model(exercise)


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(exercise_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    try:
        svc.delete_exercise(db, exercise_id)
    except svc.ExerciseNotFoundError as exc:
        raise _handle_admin_error(exc) from exc


# --- Analytics ---


@router.get("/analytics/overview", response_model=AnalyticsOverviewOut)
def get_analytics_overview(
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=90),
) -> AnalyticsOverviewOut:
    overview = analytics_service.get_overview(db, days=days)
    return AnalyticsOverviewOut.from_overview(overview)
