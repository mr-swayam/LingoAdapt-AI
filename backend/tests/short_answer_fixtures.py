"""A minimal course with one SHORT_ANSWER exercise, kept separate from
course_fixtures.py's build_lesson_with_all_types since several existing
tests hardcode that fixture's exercise count (5) - adding a 6th type there
would silently break them.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.course import Course, Exercise, ExerciseType, Language, Lesson, Skill, Unit


@dataclass
class ShortAnswerFixture:
    lesson_id: uuid.UUID
    exercise_id: uuid.UUID
    skill_id: uuid.UUID


def build_short_answer_lesson(db: Session) -> ShortAnswerFixture:
    language = Language(code="en", name="English")
    db.add(language)
    db.flush()

    course = Course(language_id=language.id, title="AI Course", description="", is_published=True)
    db.add(course)
    db.flush()

    skill = Skill(course_id=course.id, code="INTRODUCTIONS", name="Introductions")
    db.add(skill)
    db.flush()

    unit = Unit(course_id=course.id, title="Unit", position=1)
    db.add(unit)
    db.flush()

    lesson = Lesson(unit_id=unit.id, title="Introduce Yourself", position=1)
    db.add(lesson)
    db.flush()

    exercise = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.SHORT_ANSWER,
        position=1,
        prompt="Write one sentence introducing yourself.",
        payload={},
        correct_answer={
            "model_answer": "My name is Anna and I am from Spain.",
            "rubric": "Should include a name and use correct grammar for self-introduction.",
        },
        explanation=None,
        difficulty=0.4,
    )
    db.add(exercise)
    db.flush()

    db.commit()

    return ShortAnswerFixture(lesson_id=lesson.id, exercise_id=exercise.id, skill_id=skill.id)
