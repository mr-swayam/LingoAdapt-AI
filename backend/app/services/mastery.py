"""Deterministic, DB-independent learner-model arithmetic (rules.md §3: keep
the mastery algorithm isolated and replaceable). Matches the exponential
moving average documented in memory.md §8 exactly:

    old=50, correct   -> new=54
    old=50, incorrect -> new=46

Review scheduling (interval/ease/repetitions/next_review) lives in
app/services/spaced_repetition.py - a separate concern per memory.md's own
document structure (§8 Mastery Update vs §9 Spaced Repetition).
"""

# Solved from memory.md's worked example: 50*h + 100*r = 54, h+r=1 -> r=0.08.
HISTORICAL_WEIGHT = 0.92
RECENT_WEIGHT = 0.08

CONFIDENCE_FULL_AT_ATTEMPTS = 10


def compute_new_mastery(old_mastery: float, *, is_correct: bool) -> float:
    """Bounded in [0, 100] by construction (weighted average of bounded
    values) - a single answer can only ever move mastery by at most
    RECENT_WEIGHT * 100, so no single mistake or lucky guess dominates.
    """
    current_result = 100.0 if is_correct else 0.0
    new_mastery = old_mastery * HISTORICAL_WEIGHT + current_result * RECENT_WEIGHT
    return max(0.0, min(100.0, new_mastery))


def compute_confidence(attempt_count: int) -> float:
    """0-100: how much evidence backs the mastery estimate, independent of
    how high that estimate is. Reaches 100 once there have been enough
    attempts on this skill to trust the number.
    """
    return min(100.0, (attempt_count / CONFIDENCE_FULL_AT_ATTEMPTS) * 100.0)
