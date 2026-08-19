"""Course-authoring orchestration for admins (phases.md Phase 10). Every
write here is deterministic CRUD plus the structural validation in
app/services/content_validation.py - no AI is involved in creating,
editing, or publishing content, per rules.md §2.1 ("never let an LLM
directly mutate critical database state").
"""

import uuid

from sqlalchemy.orm import Session

from app.models.course import Course, Exercise, ExerciseType, Language, Lesson, Skill, Unit
from app.repositories import course_repository
from app.services.content_validation import validate_course_for_publish


class AdminContentError(Exception):
    pass


class CourseNotFoundError(AdminContentError):
    pass


class UnitNotFoundError(AdminContentError):
    pass


class LessonNotFoundError(AdminContentError):
    pass


class SkillNotFoundError(AdminContentError):
    pass


class ExerciseNotFoundError(AdminContentError):
    pass


class LanguageNotFoundError(AdminContentError):
    pass


class DuplicateLanguageCodeError(AdminContentError):
    pass


class DuplicateSkillCodeError(AdminContentError):
    pass


class CourseNotPublishableError(AdminContentError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def list_languages(db: Session) -> list[Language]:
    return course_repository.list_languages(db)


def create_language(db: Session, *, code: str, name: str) -> Language:
    if course_repository.get_language_by_code(db, code) is not None:
        raise DuplicateLanguageCodeError(code)
    language = course_repository.create_language(db, code=code, name=name)
    db.commit()
    return language


def list_courses(db: Session) -> list[Course]:
    return course_repository.list_all_courses(db)


def get_course(db: Session, course_id: uuid.UUID) -> Course:
    course = course_repository.get_course_any(db, course_id)
    if course is None:
        raise CourseNotFoundError(course_id)
    return course


def create_course(
    db: Session, *, language_id: uuid.UUID, title: str, description: str
) -> Course:
    course = course_repository.create_course(
        db, language_id=language_id, title=title, description=description
    )
    db.commit()
    return course


def update_course(
    db: Session, course_id: uuid.UUID, *, title: str | None, description: str | None
) -> Course:
    course = get_course(db, course_id)
    course_repository.update_course(db, course, title=title, description=description)
    db.commit()
    return course


def delete_course(db: Session, course_id: uuid.UUID) -> None:
    course = get_course(db, course_id)
    course_repository.delete_course(db, course)
    db.commit()


def publish_course(db: Session, course_id: uuid.UUID) -> Course:
    course = get_course(db, course_id)
    errors = validate_course_for_publish(course)
    if errors:
        raise CourseNotPublishableError(errors)
    course_repository.set_course_published(db, course, is_published=True)
    db.commit()
    return course


def unpublish_course(db: Session, course_id: uuid.UUID) -> Course:
    course = get_course(db, course_id)
    course_repository.set_course_published(db, course, is_published=False)
    db.commit()
    return course


def create_unit(db: Session, *, course_id: uuid.UUID, title: str, position: int | None) -> Unit:
    get_course(db, course_id)  # 404 if the course doesn't exist
    unit = course_repository.create_unit(db, course_id=course_id, title=title, position=position)
    db.commit()
    return unit


def _get_unit(db: Session, unit_id: uuid.UUID) -> Unit:
    unit = course_repository.get_unit(db, unit_id)
    if unit is None:
        raise UnitNotFoundError(unit_id)
    return unit


def update_unit(
    db: Session, unit_id: uuid.UUID, *, title: str | None, position: int | None
) -> Unit:
    unit = _get_unit(db, unit_id)
    course_repository.update_unit(db, unit, title=title, position=position)
    db.commit()
    return unit


def delete_unit(db: Session, unit_id: uuid.UUID) -> None:
    unit = _get_unit(db, unit_id)
    course_repository.delete_unit(db, unit)
    db.commit()


def create_lesson(db: Session, *, unit_id: uuid.UUID, title: str, position: int | None) -> Lesson:
    _get_unit(db, unit_id)
    lesson = course_repository.create_lesson(db, unit_id=unit_id, title=title, position=position)
    db.commit()
    return lesson


def _get_lesson(db: Session, lesson_id: uuid.UUID) -> Lesson:
    lesson = course_repository.get_lesson_any(db, lesson_id)
    if lesson is None:
        raise LessonNotFoundError(lesson_id)
    return lesson


def get_lesson(db: Session, lesson_id: uuid.UUID) -> Lesson:
    return _get_lesson(db, lesson_id)


def update_lesson(
    db: Session, lesson_id: uuid.UUID, *, title: str | None, position: int | None
) -> Lesson:
    lesson = _get_lesson(db, lesson_id)
    course_repository.update_lesson(db, lesson, title=title, position=position)
    db.commit()
    return lesson


def delete_lesson(db: Session, lesson_id: uuid.UUID) -> None:
    lesson = _get_lesson(db, lesson_id)
    course_repository.delete_lesson(db, lesson)
    db.commit()


def create_skill(db: Session, *, course_id: uuid.UUID, code: str, name: str) -> Skill:
    get_course(db, course_id)
    existing = {s.code for s in course_repository.list_skills_for_course(db, course_id)}
    if code in existing:
        raise DuplicateSkillCodeError(code)
    skill = course_repository.create_skill(db, course_id=course_id, code=code, name=name)
    db.commit()
    return skill


def _get_skill(db: Session, skill_id: uuid.UUID) -> Skill:
    skill = course_repository.get_skill(db, skill_id)
    if skill is None:
        raise SkillNotFoundError(skill_id)
    return skill


def update_skill(db: Session, skill_id: uuid.UUID, *, name: str | None) -> Skill:
    skill = _get_skill(db, skill_id)
    course_repository.update_skill(db, skill, name=name)
    db.commit()
    return skill


def list_skills_for_course(db: Session, course_id: uuid.UUID) -> list[Skill]:
    get_course(db, course_id)
    return course_repository.list_skills_for_course(db, course_id)


def _get_exercise(db: Session, exercise_id: uuid.UUID) -> Exercise:
    exercise = course_repository.get_exercise(db, exercise_id)
    if exercise is None:
        raise ExerciseNotFoundError(exercise_id)
    return exercise


def create_exercise(
    db: Session,
    *,
    lesson_id: uuid.UUID,
    skill_id: uuid.UUID,
    type: ExerciseType,
    prompt: str,
    payload: dict,
    correct_answer: dict,
    explanation: str | None,
    difficulty: float,
    position: int | None,
    options: list[dict],
) -> Exercise:
    _get_lesson(db, lesson_id)
    _get_skill(db, skill_id)
    exercise = course_repository.create_exercise(
        db,
        lesson_id=lesson_id,
        skill_id=skill_id,
        type=type,
        prompt=prompt,
        payload=payload,
        correct_answer=correct_answer,
        explanation=explanation,
        difficulty=difficulty,
        position=position,
    )
    course_repository.replace_exercise_options(db, exercise, options)
    db.commit()
    return _get_exercise(db, exercise.id)


def update_exercise(
    db: Session,
    exercise_id: uuid.UUID,
    *,
    skill_id: uuid.UUID | None,
    prompt: str | None,
    payload: dict | None,
    correct_answer: dict | None,
    explanation: str | None,
    explanation_set: bool,
    difficulty: float | None,
    position: int | None,
    options: list[dict] | None,
) -> Exercise:
    exercise = _get_exercise(db, exercise_id)
    if skill_id is not None:
        _get_skill(db, skill_id)
    course_repository.update_exercise(
        db,
        exercise,
        skill_id=skill_id,
        prompt=prompt,
        payload=payload,
        correct_answer=correct_answer,
        explanation=explanation,
        explanation_set=explanation_set,
        difficulty=difficulty,
        position=position,
    )
    if options is not None:
        course_repository.replace_exercise_options(db, exercise, options)
    db.commit()
    return _get_exercise(db, exercise.id)


def delete_exercise(db: Session, exercise_id: uuid.UUID) -> None:
    exercise = _get_exercise(db, exercise_id)
    course_repository.delete_exercise(db, exercise)
    db.commit()
