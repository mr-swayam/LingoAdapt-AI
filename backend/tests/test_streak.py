from datetime import date, timedelta

from app.services.streak import compute_streak_update

TODAY = date(2026, 8, 17)
YESTERDAY = TODAY - timedelta(days=1)


def test_first_ever_activity_starts_streak_at_one() -> None:
    update = compute_streak_update(
        current_streak=0, longest_streak=0, last_active_date=None, today=TODAY
    )
    assert update.current_streak == 1
    assert update.longest_streak == 1
    assert update.changed is True


def test_consecutive_day_increments_streak() -> None:
    update = compute_streak_update(
        current_streak=4, longest_streak=4, last_active_date=YESTERDAY, today=TODAY
    )
    assert update.current_streak == 5
    assert update.longest_streak == 5
    assert update.changed is True


def test_same_day_revisit_is_a_no_op() -> None:
    update = compute_streak_update(
        current_streak=4, longest_streak=10, last_active_date=TODAY, today=TODAY
    )
    assert update.current_streak == 4
    assert update.longest_streak == 10
    assert update.changed is False


def test_gap_of_more_than_one_day_resets_streak() -> None:
    two_days_ago = TODAY - timedelta(days=2)
    update = compute_streak_update(
        current_streak=10, longest_streak=15, last_active_date=two_days_ago, today=TODAY
    )
    assert update.current_streak == 1
    assert update.longest_streak == 15
    assert update.changed is True


def test_longest_streak_is_preserved_across_a_reset() -> None:
    two_days_ago = TODAY - timedelta(days=2)
    update = compute_streak_update(
        current_streak=1, longest_streak=20, last_active_date=two_days_ago, today=TODAY
    )
    assert update.longest_streak == 20


def test_new_current_streak_can_exceed_previous_longest() -> None:
    update = compute_streak_update(
        current_streak=5, longest_streak=5, last_active_date=YESTERDAY, today=TODAY
    )
    assert update.current_streak == 6
    assert update.longest_streak == 6
