from app.services import pronunciation


def test_identical_text_has_ratio_one() -> None:
    assert pronunciation.similarity_ratio("I would like a coffee", "I would like a coffee") == 1.0


def test_punctuation_and_casing_are_ignored() -> None:
    assert pronunciation.similarity_ratio(
        "I would like a coffee, please.", "i would like a coffee please"
    ) == 1.0


def test_one_wrong_word_reduces_ratio_but_stays_close() -> None:
    ratio = pronunciation.similarity_ratio("I would like a coffee", "I would like a tea")
    assert 0.5 < ratio < 1.0


def test_completely_different_text_has_low_ratio() -> None:
    ratio = pronunciation.similarity_ratio("I would like a coffee", "where is the train station")
    assert ratio < 0.3


def test_is_close_enough_uses_threshold() -> None:
    assert pronunciation.is_close_enough(
        "I would like a coffee please", "I would like a coffee please"
    )
    assert not pronunciation.is_close_enough(
        "I would like a coffee please", "completely unrelated words here"
    )


def test_empty_transcript_is_never_close_enough() -> None:
    assert not pronunciation.is_close_enough("I would like a coffee", "")


def test_describe_difference_reports_no_speech() -> None:
    assert "didn't hear" in pronunciation.describe_difference("hello there", "")


def test_describe_difference_reports_perfect_match() -> None:
    assert "matched" in pronunciation.describe_difference("hello there", "hello there")


def test_describe_difference_reports_word_substitution() -> None:
    note = pronunciation.describe_difference("I want a coffee", "I want a tea")
    assert "coffee" in note
    assert "tea" in note
