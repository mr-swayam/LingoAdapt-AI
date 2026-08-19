from datetime import UTC, datetime, timedelta

from app.services.spaced_repetition import (
    EASE_MIN,
    EASE_START,
    MAX_INTERVAL_DAYS,
    compute_review_schedule,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_first_correct_answer_schedules_review_tomorrow() -> None:
    schedule = compute_review_schedule(
        ease_factor=EASE_START, repetitions=0, interval_days=0, is_correct=True, now=NOW
    )
    assert schedule.repetitions == 1
    assert schedule.interval_days == 1
    assert schedule.next_review_at == NOW + timedelta(days=1)


def test_second_correct_answer_schedules_three_days_out() -> None:
    schedule = compute_review_schedule(
        ease_factor=EASE_START, repetitions=1, interval_days=1, is_correct=True, now=NOW
    )
    assert schedule.repetitions == 2
    assert schedule.interval_days == 3


def test_third_correct_answer_grows_interval_by_ease_factor() -> None:
    schedule = compute_review_schedule(
        ease_factor=2.6, repetitions=2, interval_days=3, is_correct=True, now=NOW
    )
    assert schedule.repetitions == 3
    assert schedule.interval_days == round(3 * 2.6)


def test_incorrect_answer_resets_repetitions_and_shortens_interval() -> None:
    schedule = compute_review_schedule(
        ease_factor=3.0, repetitions=5, interval_days=60, is_correct=False, now=NOW
    )
    assert schedule.repetitions == 0
    assert schedule.interval_days == 1
    assert schedule.next_review_at == NOW + timedelta(days=1)


def test_ease_factor_increases_on_correct_and_is_floored() -> None:
    schedule = compute_review_schedule(
        ease_factor=EASE_START, repetitions=1, interval_days=1, is_correct=True, now=NOW
    )
    assert schedule.ease_factor == EASE_START + 0.1


def test_ease_factor_cannot_drop_below_floor() -> None:
    schedule = compute_review_schedule(
        ease_factor=EASE_MIN, repetitions=3, interval_days=10, is_correct=False, now=NOW
    )
    assert schedule.ease_factor == EASE_MIN


def test_interval_never_exceeds_the_cap_even_after_many_correct_streaks() -> None:
    """Regression test: interval = round(interval * ease) compounds
    exponentially with sustained streaks and would otherwise eventually
    overflow datetime's range (this genuinely happened - a 20-correct-answer
    streak raised an OverflowError before this cap was added).
    """
    ease = EASE_START
    interval = 0
    repetitions = 0
    for _ in range(50):
        schedule = compute_review_schedule(
            ease_factor=ease, repetitions=repetitions, interval_days=interval,
            is_correct=True, now=NOW,
        )
        ease = schedule.ease_factor
        interval = schedule.interval_days
        repetitions = schedule.repetitions
        assert interval <= MAX_INTERVAL_DAYS
