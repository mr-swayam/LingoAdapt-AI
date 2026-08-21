"""Unit tests for app.services.listening_evaluation.classify_listening_answer -
deterministic, no DB/AI needed. Mirrors tests/test_pronunciation.py's style
if one exists; otherwise follows this project's convention of testing
service-layer logic directly, not just through the API."""

from app.services.listening_evaluation import ListeningCategory, classify_listening_answer

EXPECTED = "I would like a glass of water, please."


def test_exact_match_is_exact() -> None:
    result = classify_listening_answer(EXPECTED, EXPECTED)
    assert result.category == ListeningCategory.EXACT
    assert result.is_correct is True
    assert result.words_missing == []
    assert result.words_incorrect == []


def test_punctuation_and_case_only_difference_is_normalized() -> None:
    result = classify_listening_answer(EXPECTED, "i would like a glass of water please")
    assert result.category == ListeningCategory.NORMALIZED
    assert result.is_correct is True


def test_extra_whitespace_only_difference_is_normalized() -> None:
    result = classify_listening_answer(EXPECTED, "I  would like a glass of   water, please.")
    assert result.category == ListeningCategory.NORMALIZED
    assert result.is_correct is True


def test_single_word_typo_is_minor_error_and_still_correct() -> None:
    result = classify_listening_answer(EXPECTED, "I would like a glas of water, please.")
    assert result.category == ListeningCategory.MINOR_ERROR
    assert result.is_correct is True
    assert "glass" in result.words_missing
    assert "glas" in result.words_incorrect


def test_missing_one_non_critical_word_is_minor_error() -> None:
    result = classify_listening_answer(EXPECTED, "I would like glass of water please")
    assert result.category == ListeningCategory.MINOR_ERROR
    assert result.is_correct is True
    assert "a" in result.words_missing


def test_partial_transcription_is_partial_and_incorrect_for_scoring() -> None:
    result = classify_listening_answer(EXPECTED, "I would like a glass")
    assert result.category == ListeningCategory.PARTIAL
    assert result.is_correct is False
    assert "of" in result.words_missing
    assert "water" in result.words_missing


def test_mostly_wrong_answer_is_major_error() -> None:
    result = classify_listening_answer(EXPECTED, "yesterday I go to school")
    assert result.category == ListeningCategory.MAJOR_ERROR
    assert result.is_correct is False


def test_empty_submission_is_incorrect() -> None:
    result = classify_listening_answer(EXPECTED, "")
    assert result.category == ListeningCategory.INCORRECT
    assert result.is_correct is False
    assert result.words_missing == [
        "i", "would", "like", "a", "glass", "of", "water", "please",
    ]


def test_whitespace_only_submission_is_incorrect() -> None:
    result = classify_listening_answer(EXPECTED, "   ")
    assert result.category == ListeningCategory.INCORRECT
    assert result.is_correct is False


def test_completely_unrelated_answer_is_incorrect_or_major_error_never_correct() -> None:
    result = classify_listening_answer(EXPECTED, "xyz qwerty asdf")
    assert result.is_correct is False
    assert result.category in {ListeningCategory.MAJOR_ERROR, ListeningCategory.INCORRECT}


def test_expected_sentence_is_never_altered_by_evaluation() -> None:
    """rules.md invariant: the expected answer is the fixed source of
    truth - it must be echoed back verbatim, never rewritten based on what
    the learner typed."""
    result = classify_listening_answer(EXPECTED, "totally different text")
    assert result.expected_sentence == EXPECTED
