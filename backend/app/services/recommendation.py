"""Deterministic skill-priority scoring for personalized practice
(architecture.md §9). No LLM involved, per that section's explicit rule.

architecture.md's formula lists six terms:
    weakness + review_due + recent_mistakes + lesson_progress + learner_goal
    - excessive_repetition

This implements weakness, review_due, and recent_mistakes as literal scored
terms below. The other three are handled structurally rather than as
weighted numbers, and that's a deliberate simplification, not an oversight:
- lesson_progress: candidate skills are scoped to ones the learner has
  actually practiced before (has a skill_mastery row) - you can't get
  personalized practice on content you've never touched, which is the
  practical effect this term is meant to have.
- learner_goal: not used as a per-skill weight; a practice session's size is
  fixed rather than dynamically sized to the daily XP goal.
- excessive_repetition: a practice session takes at most one exercise per
  skill (app/services/practice_service.py), which structurally prevents
  drilling the same skill repeatedly within one session, without needing a
  numeric penalty term.
"""

import uuid
from dataclasses import dataclass

REVIEW_DUE_BONUS = 50.0
RECENT_MISTAKE_WEIGHT = 15.0


@dataclass(frozen=True)
class SkillCandidate:
    skill_id: uuid.UUID
    mastery: float
    is_review_due: bool
    recent_incorrect_count: int


def compute_skill_priority(candidate: SkillCandidate) -> float:
    weakness = 100.0 - candidate.mastery
    review_bonus = REVIEW_DUE_BONUS if candidate.is_review_due else 0.0
    mistake_bonus = candidate.recent_incorrect_count * RECENT_MISTAKE_WEIGHT
    return weakness + review_bonus + mistake_bonus


def rank_skills(candidates: list[SkillCandidate], *, limit: int) -> list[SkillCandidate]:
    ranked = sorted(candidates, key=compute_skill_priority, reverse=True)
    return ranked[:limit]
