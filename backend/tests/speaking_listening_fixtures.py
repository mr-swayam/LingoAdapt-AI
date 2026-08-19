"""A minimal course with one SPEAKING and one LISTENING exercise, mirroring
short_answer_fixtures.py's pattern for Phase 8's voice-graded exercise types.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.course import Course, Exercise, ExerciseType, Language, Lesson, Skill, Unit


@dataclass
class SpeakingListeningFixture:
    lesson_id: uuid.UUID
    speaking_exercise_id: uuid.UUID
    listening_exercise_id: uuid.UUID
    skill_id: uuid.UUID


def build_speaking_listening_lesson(db: Session) -> SpeakingListeningFixture:
    language = Language(code="en", name="English")
    db.add(language)
    db.flush()

    course = Course(
        language_id=language.id, title="Voice Course", description="", is_published=True
    )
    db.add(course)
    db.flush()

    skill = Skill(course_id=course.id, code="RESTAURANT_PHRASES", name="Restaurant Phrases")
    db.add(skill)
    db.flush()

    unit = Unit(course_id=course.id, title="Unit", position=1)
    db.add(unit)
    db.flush()

    lesson = Lesson(unit_id=unit.id, title="Speak and Listen", position=1)
    db.add(lesson)
    db.flush()

    speaking = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.SPEAKING,
        position=1,
        prompt="Say the following sentence aloud:",
        payload={"phrase_to_say": "Can I have the bill, please?"},
        correct_answer={"answers": ["Can I have the bill, please?", "Can I have the bill please"]},
        explanation="A polite, complete request.",
        difficulty=0.3,
    )
    db.add(speaking)
    db.flush()

    listening = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.LISTENING,
        position=2,
        prompt="Listen to the audio and type what you hear.",
        payload={},
        correct_answer={
            "text_to_speak": "I would like a glass of water, please.",
            "answers": [
                "I would like a glass of water, please.",
                "I would like a glass of water please",
            ],
        },
        explanation=None,
        difficulty=0.3,
    )
    db.add(listening)
    db.flush()

    db.commit()

    return SpeakingListeningFixture(
        lesson_id=lesson.id,
        speaking_exercise_id=speaking.id,
        listening_exercise_id=listening.id,
        skill_id=skill.id,
    )
