"""Deterministic comparison between a LISTENING exercise's dictation target
and what the learner typed. Same rationale as app/services/pronunciation.py
(rules.md §2: never let an LLM determine correctness) - the difference is
that a typed answer deserves a richer, more informative category than
SPEAKING's single "close enough or not" threshold, since there's no STT
noise to average away, just genuine differences between what was expected
and what was typed. Reuses pronunciation.py's word-normalization approach
rather than duplicating it.
"""

import difflib
import enum
from dataclasses import dataclass, field

from app.services.pronunciation import normalize_words, similarity_ratio

# Tuned the same way pronunciation.CORRECT_THRESHOLD was: by what a listener
# would genuinely call "a small typo" vs. "actually missed a word" in the
# 5-10 word dictation sentences this exercise type uses, not a formula
# derived first-principles.
MINOR_ERROR_THRESHOLD = 0.85
PARTIAL_THRESHOLD = 0.5


class ListeningCategory(enum.StrEnum):
    EXACT = "EXACT"
    NORMALIZED = "NORMALIZED"
    MINOR_ERROR = "MINOR_ERROR"
    PARTIAL = "PARTIAL"
    MAJOR_ERROR = "MAJOR_ERROR"
    INCORRECT = "INCORRECT"


# Categories lenient enough to count as a correct answer for XP/mastery -
# mirrors pronunciation.CORRECT_THRESHOLD's tolerance for input-channel
# noise: a keyboard typo is the typing equivalent of an STT artifact, not a
# real listening-comprehension failure.
_CORRECT_CATEGORIES = frozenset(
    {ListeningCategory.EXACT, ListeningCategory.NORMALIZED, ListeningCategory.MINOR_ERROR}
)


@dataclass
class ListeningEvaluation:
    category: ListeningCategory
    is_correct: bool
    expected_sentence: str
    words_correct: list[str] = field(default_factory=list)
    words_missing: list[str] = field(default_factory=list)
    words_incorrect: list[str] = field(default_factory=list)
    explanation: str = ""


def _word_diff(expected_words: list[str], submitted_words: list[str]) -> tuple[
    list[str], list[str], list[str]
]:
    """Opcode-based word bucketing, same technique as
    pronunciation.describe_difference - correct (equal), missing (only in
    expected), incorrect (only in submitted, i.e. wrong words typed)."""
    matcher = difflib.SequenceMatcher(None, expected_words, submitted_words)
    correct: list[str] = []
    missing: list[str] = []
    incorrect: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            correct.extend(expected_words[i1:i2])
        else:
            missing.extend(expected_words[i1:i2])
            incorrect.extend(submitted_words[j1:j2])
    return correct, missing, incorrect


def _describe(category: ListeningCategory, missing: list[str], incorrect: list[str]) -> str:
    if category == ListeningCategory.EXACT:
        return "Perfect - exactly right!"
    if category == ListeningCategory.NORMALIZED:
        return "Correct! (Only capitalization, punctuation, or spacing differed.)"
    if category == ListeningCategory.INCORRECT:
        return "We didn't catch a real answer - try listening again."

    parts: list[str] = []
    if incorrect:
        parts.append(f"you wrote \"{' '.join(incorrect)}\"")
    if missing:
        parts.append(f"missed \"{' '.join(missing)}\"")
    detail = "; ".join(parts) if parts else "some words didn't match"

    if category == ListeningCategory.MINOR_ERROR:
        return f"Close - just a small slip: {detail}."
    if category == ListeningCategory.PARTIAL:
        return f"Partially correct - {detail}."
    return f"Not quite - {detail}."


def classify_listening_answer(expected: str, submitted: str) -> ListeningEvaluation:
    """The expected sentence and submitted text are the sole source of
    truth - this is plain string/word comparison, no AI involved."""
    expected_words = normalize_words(expected)
    submitted_words = normalize_words(submitted)

    if not submitted_words:
        return ListeningEvaluation(
            category=ListeningCategory.INCORRECT,
            is_correct=False,
            expected_sentence=expected,
            words_missing=expected_words,
            explanation=_describe(ListeningCategory.INCORRECT, [], []),
        )

    if submitted.strip() == expected.strip():
        category = ListeningCategory.EXACT
    elif " ".join(submitted_words) == " ".join(expected_words):
        category = ListeningCategory.NORMALIZED
    else:
        ratio = similarity_ratio(expected, submitted)
        if ratio >= MINOR_ERROR_THRESHOLD:
            category = ListeningCategory.MINOR_ERROR
        elif ratio >= PARTIAL_THRESHOLD:
            category = ListeningCategory.PARTIAL
        else:
            category = ListeningCategory.MAJOR_ERROR

    correct, missing, incorrect = _word_diff(expected_words, submitted_words)

    return ListeningEvaluation(
        category=category,
        is_correct=category in _CORRECT_CATEGORIES,
        expected_sentence=expected,
        words_correct=correct,
        words_missing=missing,
        words_incorrect=incorrect,
        explanation=_describe(category, missing, incorrect),
    )
