from app.services.mastery import compute_confidence, compute_new_mastery


def test_matches_memory_md_worked_example_correct() -> None:
    # memory.md §8: "Old mastery: 50, Current correct answer: 1, New mastery: 54"
    assert compute_new_mastery(50.0, is_correct=True) == 54.0


def test_matches_memory_md_worked_example_incorrect() -> None:
    # memory.md §8: "Old mastery: 50, Current incorrect answer: 0, New mastery: 46"
    assert compute_new_mastery(50.0, is_correct=False) == 46.0


def test_mastery_is_bounded_at_100() -> None:
    result = compute_new_mastery(99.0, is_correct=True)
    assert result <= 100.0


def test_mastery_is_bounded_at_0() -> None:
    result = compute_new_mastery(1.0, is_correct=False)
    assert result >= 0.0


def test_single_correct_answer_from_zero_does_not_imply_mastery() -> None:
    # rules.md §3.9: a single correct answer should not imply mastery.
    result = compute_new_mastery(0.0, is_correct=True)
    assert result < 10.0


def test_single_mistake_does_not_drastically_change_high_mastery() -> None:
    # rules.md §3.8: a single mistake should not drastically change mastery.
    result = compute_new_mastery(90.0, is_correct=False)
    assert result > 80.0


def test_confidence_grows_linearly_with_attempts() -> None:
    assert compute_confidence(0) == 0.0
    assert compute_confidence(5) == 50.0
    assert compute_confidence(10) == 100.0


def test_confidence_caps_at_100_beyond_threshold() -> None:
    assert compute_confidence(50) == 100.0
