"""A minimal course plus the grammar skill catalog conversation corrections
resolve against, mirroring app.seed.GRAMMAR_SKILLS without depending on
the seed script (tests build their own isolated fixtures)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.course import Course, Language, Skill

GRAMMAR_SKILL_CODES = [
    "PAST_TENSE",
    "PREPOSITIONS",
    "ARTICLES",
    "SUBJECT_VERB_AGREEMENT",
    "PLURALS",
    "WORD_CHOICE",
    "GENERAL",
]


@dataclass
class GrammarSkillsFixture:
    course_id: uuid.UUID
    skill_ids: dict[str, uuid.UUID]


def build_grammar_skills(db: Session) -> GrammarSkillsFixture:
    language = Language(code="en", name="English")
    db.add(language)
    db.flush()

    course = Course(language_id=language.id, title="AI Course", description="", is_published=True)
    db.add(course)
    db.flush()

    skill_ids: dict[str, uuid.UUID] = {}
    for code in GRAMMAR_SKILL_CODES:
        skill = Skill(course_id=course.id, code=code, name=code.replace("_", " ").title())
        db.add(skill)
        db.flush()
        skill_ids[code] = skill.id

    db.commit()

    return GrammarSkillsFixture(course_id=course.id, skill_ids=skill_ids)
