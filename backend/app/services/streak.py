"""Deterministic streak arithmetic, isolated from the DB so it's trivially
unit-testable and easy to replace later (per rules.md: keep the algorithm
replaceable, a single mistake/day-off shouldn't be punished excessively).
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class StreakUpdate:
    current_streak: int
    longest_streak: int
    changed: bool  # False if today was already counted (no-op re-visit)


def compute_streak_update(
    *,
    current_streak: int,
    longest_streak: int,
    last_active_date: date | None,
    today: date,
) -> StreakUpdate:
    if last_active_date == today:
        return StreakUpdate(current_streak, longest_streak, changed=False)

    if last_active_date == today - timedelta(days=1):
        new_current = current_streak + 1
    else:
        # First-ever activity, or a gap of more than one day: streak resets.
        new_current = 1

    new_longest = max(longest_streak, new_current)
    return StreakUpdate(new_current, new_longest, changed=True)
