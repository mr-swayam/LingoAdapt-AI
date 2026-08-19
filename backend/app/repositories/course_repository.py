import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.course import (
    Course,
    Exercise,
    ExerciseOption,
    ExerciseType,
    Language,
    Lesson,
    Skill,
    Unit,
)


def list_published_courses(db: Session) -> list[Course]:
    stmt = (
        select(Course)
        .where(Course.is_published.is_(True))
        .options(joinedload(Course.language), selectinload(Course.units).selectinload(Unit.lessons))
        .order_by(Course.title)
    )
    return list(db.execute(stmt).unique().scalars().all())


def get_course_detail(db: Session, course_id: uuid.UUID) -> Course | None:
    stmt = (
        select(Course)
        .where(Course.id == course_id, Course.is_published.is_(True))
        .options(joinedload(Course.language), selectinload(Course.units).selectinload(Unit.lessons))
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def get_lesson(db: Session, lesson_id: uuid.UUID) -> Lesson | None:
    stmt = (
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(selectinload(Lesson.exercises).selectinload(Exercise.options))
    )
    return db.execute(stmt).scalar_one_or_none()


def get_exercise(db: Session, exercise_id: uuid.UUID) -> Exercise | None:
    stmt = (
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.options))
    )
    return db.execute(stmt).scalar_one_or_none()


def list_exercises_for_skill(db: Session, skill_id: uuid.UUID) -> list[Exercise]:
    stmt = (
        select(Exercise)
        .where(Exercise.skill_id == skill_id)
        .options(selectinload(Exercise.options))
    )
    return list(db.execute(stmt).scalars().all())


def get_skill_by_code(db: Session, code: str) -> Skill | None:
    """Skill codes are unique per-course, not globally, but the seed data
    only ever creates one course - fine for resolving the AI tutor's
    normalized skill string (Phase 7) back to a row without threading a
    course_id through the whole conversation flow.
    """
    stmt = select(Skill).where(Skill.code == code)
    return db.execute(stmt).scalars().first()


# --- Admin content authoring (Phase 10) ---
# Unlike the learner-facing functions above, these are never filtered to
# is_published - an admin needs to see and edit draft content too.


def list_languages(db: Session) -> list[Language]:
    return list(db.execute(select(Language).order_by(Language.name)).scalars().all())


def get_language_by_code(db: Session, code: str) -> Language | None:
    return db.execute(select(Language).where(Language.code == code)).scalar_one_or_none()


def create_language(db: Session, *, code: str, name: str) -> Language:
    language = Language(code=code, name=name)
    db.add(language)
    db.flush()
    return language


def list_all_courses(db: Session) -> list[Course]:
    stmt = (
        select(Course)
        .options(joinedload(Course.language), selectinload(Course.units).selectinload(Unit.lessons))
        .order_by(Course.created_at.desc())
    )
    return list(db.execute(stmt).unique().scalars().all())


def get_course_any(db: Session, course_id: uuid.UUID) -> Course | None:
    """Like get_course_detail, but not filtered to published - for admin editing."""
    stmt = (
        select(Course)
        .where(Course.id == course_id)
        .options(
            joinedload(Course.language),
            selectinload(Course.units).selectinload(Unit.lessons).selectinload(Lesson.exercises),
            selectinload(Course.skills),
        )
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def create_course(
    db: Session, *, language_id: uuid.UUID, title: str, description: str
) -> Course:
    course = Course(
        language_id=language_id, title=title, description=description, is_published=False
    )
    db.add(course)
    db.flush()
    return course


def update_course(
    db: Session, course: Course, *, title: str | None, description: str | None
) -> Course:
    if title is not None:
        course.title = title
    if description is not None:
        course.description = description
    db.flush()
    return course


def set_course_published(db: Session, course: Course, *, is_published: bool) -> Course:
    course.is_published = is_published
    db.flush()
    return course


def delete_course(db: Session, course: Course) -> None:
    db.delete(course)
    db.flush()


def _next_position(existing_positions: list[int]) -> int:
    return (max(existing_positions) + 1) if existing_positions else 1


def create_unit(
    db: Session, *, course_id: uuid.UUID, title: str, position: int | None
) -> Unit:
    if position is None:
        existing = db.execute(
            select(Unit.position).where(Unit.course_id == course_id)
        ).scalars().all()
        position = _next_position(list(existing))
    unit = Unit(course_id=course_id, title=title, position=position)
    db.add(unit)
    db.flush()
    return unit


def get_unit(db: Session, unit_id: uuid.UUID) -> Unit | None:
    return db.get(Unit, unit_id)


def update_unit(db: Session, unit: Unit, *, title: str | None, position: int | None) -> Unit:
    if title is not None:
        unit.title = title
    if position is not None:
        unit.position = position
    db.flush()
    return unit


def delete_unit(db: Session, unit: Unit) -> None:
    db.delete(unit)
    db.flush()


def create_lesson(db: Session, *, unit_id: uuid.UUID, title: str, position: int | None) -> Lesson:
    if position is None:
        existing = db.execute(
            select(Lesson.position).where(Lesson.unit_id == unit_id)
        ).scalars().all()
        position = _next_position(list(existing))
    lesson = Lesson(unit_id=unit_id, title=title, position=position)
    db.add(lesson)
    db.flush()
    return lesson


def update_lesson(
    db: Session, lesson: Lesson, *, title: str | None, position: int | None
) -> Lesson:
    if title is not None:
        lesson.title = title
    if position is not None:
        lesson.position = position
    db.flush()
    return lesson


def delete_lesson(db: Session, lesson: Lesson) -> None:
    db.delete(lesson)
    db.flush()


def get_lesson_any(db: Session, lesson_id: uuid.UUID) -> Lesson | None:
    stmt = (
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.exercises).selectinload(Exercise.options),
            joinedload(Lesson.unit),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def create_skill(db: Session, *, course_id: uuid.UUID, code: str, name: str) -> Skill:
    skill = Skill(course_id=course_id, code=code, name=name)
    db.add(skill)
    db.flush()
    return skill


def get_skill(db: Session, skill_id: uuid.UUID) -> Skill | None:
    return db.get(Skill, skill_id)


def update_skill(db: Session, skill: Skill, *, name: str | None) -> Skill:
    if name is not None:
        skill.name = name
    db.flush()
    return skill


def list_skills_for_course(db: Session, course_id: uuid.UUID) -> list[Skill]:
    stmt = select(Skill).where(Skill.course_id == course_id).order_by(Skill.code)
    return list(db.execute(stmt).scalars().all())


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
) -> Exercise:
    if position is None:
        existing = db.execute(
            select(Exercise.position).where(Exercise.lesson_id == lesson_id)
        ).scalars().all()
        position = _next_position(list(existing))
    exercise = Exercise(
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
    db.add(exercise)
    db.flush()
    return exercise


def update_exercise(
    db: Session,
    exercise: Exercise,
    *,
    skill_id: uuid.UUID | None,
    prompt: str | None,
    payload: dict | None,
    correct_answer: dict | None,
    explanation: str | None,
    explanation_set: bool,
    difficulty: float | None,
    position: int | None,
) -> Exercise:
    if skill_id is not None:
        exercise.skill_id = skill_id
    if prompt is not None:
        exercise.prompt = prompt
    if payload is not None:
        exercise.payload = payload
    if correct_answer is not None:
        exercise.correct_answer = correct_answer
    if explanation_set:
        exercise.explanation = explanation
    if difficulty is not None:
        exercise.difficulty = difficulty
    if position is not None:
        exercise.position = position
    db.flush()
    return exercise


def delete_exercise(db: Session, exercise: Exercise) -> None:
    db.delete(exercise)
    db.flush()


def replace_exercise_options(
    db: Session, exercise: Exercise, options: list[dict]
) -> list[ExerciseOption]:
    """Options are authored as a whole set at once (an exercise's option
    list is small and edited together in the admin UI), so replacing them
    wholesale on every save is simpler and less error-prone than diffing
    add/update/remove - cascade delete-orphan on the relationship handles
    cleanup of the old rows."""
    exercise.options.clear()
    db.flush()
    new_options = []
    for position, opt in enumerate(options, start=1):
        option = ExerciseOption(
            exercise_id=exercise.id,
            position=position,
            text=opt["text"],
            is_correct=opt.get("is_correct"),
            correct_position=opt.get("correct_position"),
            match_group=opt.get("match_group"),
            match_key=opt.get("match_key"),
        )
        db.add(option)
        new_options.append(option)
    db.flush()
    return new_options
