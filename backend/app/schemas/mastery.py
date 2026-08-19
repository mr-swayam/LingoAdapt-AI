from datetime import datetime

from pydantic import BaseModel

from app.models.learner_model import SkillMastery

STRONG_THRESHOLD = 70.0
WEAK_THRESHOLD = 40.0


def mastery_level(mastery: float) -> str:
    if mastery >= STRONG_THRESHOLD:
        return "strong"
    if mastery < WEAK_THRESHOLD:
        return "weak"
    return "developing"


class SkillMasteryOut(BaseModel):
    skill_code: str
    skill_name: str
    mastery: float
    confidence: float
    level: str
    attempt_count: int
    correct_count: int
    last_practiced_at: datetime | None
    next_review_at: datetime | None

    @classmethod
    def from_model(cls, row: SkillMastery) -> "SkillMasteryOut":
        return cls(
            skill_code=row.skill.code,
            skill_name=row.skill.name,
            mastery=round(row.mastery, 1),
            confidence=round(row.confidence, 1),
            level=mastery_level(row.mastery),
            attempt_count=row.attempt_count,
            correct_count=row.correct_count,
            last_practiced_at=row.last_practiced_at,
            next_review_at=row.next_review_at,
        )


class ReviewItemOut(BaseModel):
    skill_code: str
    skill_name: str
    mastery: float
    next_review_at: datetime

    @classmethod
    def from_model(cls, row: SkillMastery) -> "ReviewItemOut":
        assert row.next_review_at is not None
        return cls(
            skill_code=row.skill.code,
            skill_name=row.skill.name,
            mastery=round(row.mastery, 1),
            next_review_at=row.next_review_at,
        )
