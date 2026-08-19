"""Builds the compact learner context object memory.md §5 requires before
every AI tutor call - deliberately NOT a dump of the learner's full history
(memory.md: "Do not send the entire database history to the model").
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.conversation import ConversationScenario
from app.repositories import evaluation_repository, learner_model_repository

# Minimum attempts before a skill counts as "weak" or "strong" - guards
# against a single lucky/unlucky answer producing a misleading label.
MIN_ATTEMPTS_FOR_SIGNAL = 3
WEAK_SKILL_THRESHOLD = 50.0
STRONG_SKILL_THRESHOLD = 80.0
MAX_SKILLS_PER_BUCKET = 5
MAX_RECENT_ERRORS = 5

# Six-band split of the 0-100 mastery scale onto CEFR levels. Arbitrary but
# deterministic and documented - there's no ground-truth CEFR mapping to
# defer to, and rules.md forbids an LLM from making this call.
_LEVEL_BANDS: list[tuple[float, str]] = [
    (15.0, "A1"),
    (35.0, "A2"),
    (55.0, "B1"),
    (75.0, "B2"),
    (90.0, "C1"),
]
_TOP_LEVEL = "C2"


def estimate_level(average_mastery: float) -> str:
    for ceiling, level in _LEVEL_BANDS:
        if average_mastery < ceiling:
            return level
    return _TOP_LEVEL


@dataclass(frozen=True)
class LearnerContext:
    target_language: str
    estimated_level: str
    current_topic: str
    weak_skills: list[str]
    strong_skills: list[str]
    recent_errors: list[str]

    def to_prompt_dict(self) -> dict:
        return {
            "target_language": self.target_language,
            "estimated_level": self.estimated_level,
            "current_topic": self.current_topic,
            "weak_skills": self.weak_skills,
            "recent_errors": self.recent_errors,
            "strong_skills": self.strong_skills,
        }


def build_learner_context(
    db: Session, *, user_id: uuid.UUID, scenario: ConversationScenario
) -> LearnerContext:
    mastery_rows = learner_model_repository.list_skill_mastery_for_user(db, user_id)
    attempted = [r for r in mastery_rows if r.attempt_count >= MIN_ATTEMPTS_FOR_SIGNAL]

    average_mastery = (
        sum(r.mastery for r in attempted) / len(attempted) if attempted else 0.0
    )

    weak = sorted(
        (r for r in attempted if r.mastery < WEAK_SKILL_THRESHOLD), key=lambda r: r.mastery
    )
    strong = sorted(
        (r for r in attempted if r.mastery >= STRONG_SKILL_THRESHOLD),
        key=lambda r: -r.mastery,
    )

    recent_errors = evaluation_repository.list_recent_errors(
        db, user_id, limit=MAX_RECENT_ERRORS
    )

    return LearnerContext(
        target_language="English",
        estimated_level=estimate_level(average_mastery),
        current_topic=scenario.value.replace("_", " ").title(),
        weak_skills=[r.skill.code for r in weak[:MAX_SKILLS_PER_BUCKET]],
        strong_skills=[r.skill.code for r in strong[:MAX_SKILLS_PER_BUCKET]],
        recent_errors=[e.description for e in recent_errors],
    )
