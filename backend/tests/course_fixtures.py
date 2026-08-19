"""Builds a small in-transaction course/lesson fixture covering all 5 exercise types."""

import uuid
from dataclasses import dataclass

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


@dataclass
class SeededLesson:
    lesson_id: uuid.UUID
    exercise_ids: dict[ExerciseType, uuid.UUID]
    option_ids: dict[ExerciseType, dict[str, uuid.UUID]]


def build_lesson_with_all_types(db: Session) -> SeededLesson:
    language = Language(code="en", name="English")
    db.add(language)
    db.flush()

    course = Course(language_id=language.id, title="Test Course", description="", is_published=True)
    db.add(course)
    db.flush()

    skill = Skill(course_id=course.id, code="TEST_SKILL", name="Test Skill")
    db.add(skill)
    db.flush()

    unit = Unit(course_id=course.id, title="Unit 1", position=1)
    db.add(unit)
    db.flush()

    lesson = Lesson(unit_id=unit.id, title="Lesson 1", position=1)
    db.add(lesson)
    db.flush()

    exercise_ids: dict[ExerciseType, uuid.UUID] = {}
    option_ids: dict[ExerciseType, dict[str, uuid.UUID]] = {}

    # MULTIPLE_CHOICE
    mc = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.MULTIPLE_CHOICE,
        position=1,
        prompt="Pick the greeting",
        payload={},
        correct_answer={},
        explanation="Hello is a greeting.",
    )
    db.add(mc)
    db.flush()
    mc_correct = ExerciseOption(exercise_id=mc.id, position=1, text="Hello", is_correct=True)
    mc_wrong = ExerciseOption(exercise_id=mc.id, position=2, text="Goodbye", is_correct=False)
    db.add_all([mc_correct, mc_wrong])
    db.flush()
    exercise_ids[ExerciseType.MULTIPLE_CHOICE] = mc.id
    option_ids[ExerciseType.MULTIPLE_CHOICE] = {"correct": mc_correct.id, "wrong": mc_wrong.id}

    # FILL_BLANK
    fb = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.FILL_BLANK,
        position=2,
        prompt="Complete the sentence",
        payload={"sentence": "___, how are you?"},
        correct_answer={"answers": ["Hello", "Hi"]},
        explanation="Both work.",
    )
    db.add(fb)
    db.flush()
    exercise_ids[ExerciseType.FILL_BLANK] = fb.id

    # TRANSLATION
    tr = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.TRANSLATION,
        position=3,
        prompt="Translate to English",
        payload={"source_text": "Hola", "source_language": "Spanish"},
        correct_answer={"answers": ["Hello", "Hi"]},
        explanation="Hola means Hello.",
    )
    db.add(tr)
    db.flush()
    exercise_ids[ExerciseType.TRANSLATION] = tr.id

    # WORD_ORDER: "Good morning"
    wo = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.WORD_ORDER,
        position=4,
        prompt="Put the words in order",
        payload={},
        correct_answer={},
        explanation="Good morning is a greeting.",
    )
    db.add(wo)
    db.flush()
    wo_good = ExerciseOption(exercise_id=wo.id, position=1, text="Good", correct_position=0)
    wo_morning = ExerciseOption(exercise_id=wo.id, position=2, text="morning", correct_position=1)
    db.add_all([wo_good, wo_morning])
    db.flush()
    exercise_ids[ExerciseType.WORD_ORDER] = wo.id
    option_ids[ExerciseType.WORD_ORDER] = {"Good": wo_good.id, "morning": wo_morning.id}

    # MATCHING: Goodbye<->Adiós, Hello<->Hola
    match = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.MATCHING,
        position=5,
        prompt="Match the words",
        payload={},
        correct_answer={},
        explanation="Direct equivalents.",
    )
    db.add(match)
    db.flush()
    left1 = ExerciseOption(
        exercise_id=match.id, position=1, text="Goodbye", match_group="left", match_key="0"
    )
    right1 = ExerciseOption(
        exercise_id=match.id, position=2, text="Adiós", match_group="right", match_key="0"
    )
    left2 = ExerciseOption(
        exercise_id=match.id, position=3, text="Hello", match_group="left", match_key="1"
    )
    right2 = ExerciseOption(
        exercise_id=match.id, position=4, text="Hola", match_group="right", match_key="1"
    )
    db.add_all([left1, right1, left2, right2])
    db.flush()
    exercise_ids[ExerciseType.MATCHING] = match.id
    option_ids[ExerciseType.MATCHING] = {
        "left1": left1.id,
        "right1": right1.id,
        "left2": left2.id,
        "right2": right2.id,
    }

    db.commit()

    return SeededLesson(lesson_id=lesson.id, exercise_ids=exercise_ids, option_ids=option_ids)
