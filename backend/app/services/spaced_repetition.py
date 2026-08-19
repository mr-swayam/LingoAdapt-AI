"""Simplified SM-2 style spaced repetition (memory.md §9: interval, ease,
repetitions, last_reviewed, next_review). Pure and DB-independent so it's
trivially testable and, per rules.md, replaceable without touching callers.

This replaces Phase 4's flat mastery-bucket next_review_at with a real
per-skill schedule that grows on repeated success and resets on failure -
"the initial algorithm can be simple" (memory.md §9), so this intentionally
skips full SM-2's 0-5 quality scale in favor of the binary correct/incorrect
signal the exercise engine actually produces.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

EASE_MIN = 1.3
EASE_START = 2.5
EASE_DELTA_CORRECT = 0.1
EASE_DELTA_INCORRECT = -0.2

# Without a cap, interval = round(interval * ease) compounds exponentially
# with sustained streaks and eventually overflows datetime's range. A year
# is already far beyond "needs regular review."
MAX_INTERVAL_DAYS = 365


@dataclass(frozen=True)
class ReviewSchedule:
    ease_factor: float
    repetitions: int
    interval_days: int
    next_review_at: datetime


def compute_review_schedule(
    *,
    ease_factor: float,
    repetitions: int,
    interval_days: int,
    is_correct: bool,
    now: datetime,
) -> ReviewSchedule:
    if not is_correct:
        # A miss resets the repetition streak and shortens the interval, but
        # doesn't punish ease as harshly as classic SM-2 - rules.md §4: "Do
        # not punish a learner excessively for one difficult question."
        new_ease = max(EASE_MIN, ease_factor + EASE_DELTA_INCORRECT)
        return ReviewSchedule(
            ease_factor=new_ease,
            repetitions=0,
            interval_days=1,
            next_review_at=now + timedelta(days=1),
        )

    new_ease = max(EASE_MIN, ease_factor + EASE_DELTA_CORRECT)
    new_repetitions = repetitions + 1

    if new_repetitions == 1:
        new_interval = 1
    elif new_repetitions == 2:
        new_interval = 3
    else:
        # Growing interval on sustained success - the core spaced-repetition
        # behavior: skills you consistently get right get reviewed less often.
        new_interval = round(interval_days * new_ease)
    new_interval = max(1, min(MAX_INTERVAL_DAYS, new_interval))

    return ReviewSchedule(
        ease_factor=new_ease,
        repetitions=new_repetitions,
        interval_days=new_interval,
        next_review_at=now + timedelta(days=new_interval),
    )
