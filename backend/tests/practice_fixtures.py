"""A course with multiple distinct skills, needed to test practice's
cross-skill selection (course_fixtures.py's single-skill fixture can't - all
its exercises share one skill, so priority ranking has nothing to rank)."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

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

SKILL_CODES = ["SKILL_A", "SKILL_B", "SKILL_C"]


@dataclass
class MultiSkillOptions:
    correct: uuid.UUID
    wrong: uuid.UUID


@dataclass
class MultiSkillFixture:
    skill_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    exercise_ids: dict[str, list[uuid.UUID]] = field(default_factory=dict)
    options: dict[uuid.UUID, MultiSkillOptions] = field(default_factory=dict)


def build_multi_skill_course(db: Session) -> MultiSkillFixture:
    language = Language(code="en", name="English")
    db.add(language)
    db.flush()

    course = Course(
        language_id=language.id, title="Multi Skill Course", description="", is_published=True
    )
    db.add(course)
    db.flush()

    unit = Unit(course_id=course.id, title="Unit", position=1)
    db.add(unit)
    db.flush()

    result = MultiSkillFixture()

    for lesson_position, skill_code in enumerate(SKILL_CODES, start=1):
        lesson = Lesson(unit_id=unit.id, title=skill_code, position=lesson_position)
        db.add(lesson)
        db.flush()

        skill = Skill(course_id=course.id, code=skill_code, name=skill_code)
        db.add(skill)
        db.flush()
        result.skill_ids[skill_code] = skill.id
        result.exercise_ids[skill_code] = []

        # Two exercises per skill at different difficulties, so adaptive
        # difficulty selection has something meaningful to choose between.
        for exercise_position, difficulty in enumerate([0.2, 0.8], start=1):
            exercise = Exercise(
                lesson_id=lesson.id,
                skill_id=skill.id,
                type=ExerciseType.MULTIPLE_CHOICE,
                position=exercise_position,
                prompt=f"{skill_code} question {exercise_position}",
                payload={},
                correct_answer={},
                explanation=f"{skill_code} explanation {exercise_position}",
                difficulty=difficulty,
            )
            db.add(exercise)
            db.flush()

            correct = ExerciseOption(
                exercise_id=exercise.id, position=1, text="Correct", is_correct=True
            )
            wrong = ExerciseOption(
                exercise_id=exercise.id, position=2, text="Wrong", is_correct=False
            )
            db.add_all([correct, wrong])
            db.flush()

            result.exercise_ids[skill_code].append(exercise.id)
            result.options[exercise.id] = MultiSkillOptions(correct=correct.id, wrong=wrong.id)

    db.commit()
    return result
