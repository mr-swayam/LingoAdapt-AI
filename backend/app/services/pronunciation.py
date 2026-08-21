"""Deterministic comparison between a SPEAKING exercise's target phrase and
the learner's transcribed speech (app/ai's transcribe()). architecture.md
§2 calls pronunciation scoring an "optional" AI capability; no provider in
this stack actually offers phoneme-level scoring, so rather than fabricate
an AI opinion about pronunciation quality, this module gives the one thing
genuinely derivable from a transcript: which words matched and which
didn't. rules.md §2: never let an LLM determine correctness - this is why
grading (word-overlap ratio, below) is plain string comparison, not an AI
judgment call.
"""

import difflib
import re
import string

# Punctuation/casing differences are already normalized away before this
# ratio is computed, and acceptable alternate phrasings are handled by
# Exercise.correct_answer["answers"] listing multiple exact targets - so
# what's left for the *fuzzy* threshold to tolerate is narrow (STT
# artifacts like a dropped filler word), not real content-word mistakes.
# 0.75 was tried first and let a single wrong content word in a 6-word
# phrase ("bill" -> "bell") through as "correct" (ratio 0.83) - caught by
# tests/test_speaking_listening.py, not just reasoned about.
CORRECT_THRESHOLD = 0.9


def normalize_words(text: str) -> list[str]:
    """Public: also reused by listening_evaluation.py, which needs the same
    casefold/punctuation-stripped word list this module already builds for
    SPEAKING transcripts."""
    stripped = text.translate(str.maketrans("", "", string.punctuation))
    return [w for w in re.split(r"\s+", stripped.strip().casefold()) if w]


def similarity_ratio(expected: str, transcript: str) -> float:
    """Word-level similarity, 0-1. Tolerant of STT noise (missing/extra
    punctuation, minor filler) that would fail an exact-match comparison,
    while still catching real word-level mistakes."""
    expected_words = normalize_words(expected)
    transcript_words = normalize_words(transcript)
    if not expected_words:
        return 0.0
    return difflib.SequenceMatcher(None, expected_words, transcript_words).ratio()


def is_close_enough(
    expected: str, transcript: str, *, threshold: float = CORRECT_THRESHOLD
) -> bool:
    return similarity_ratio(expected, transcript) >= threshold


def describe_difference(expected: str, transcript: str) -> str:
    """Short, factual, non-fabricated feedback: which words differed. No
    phonetic advice - that would require a real pronunciation model this
    stack doesn't have."""
    expected_words = normalize_words(expected)
    transcript_words = normalize_words(transcript)

    if not transcript_words:
        return "We didn't hear anything - try recording again."

    matcher = difflib.SequenceMatcher(None, expected_words, transcript_words)
    mismatches: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        expected_chunk = " ".join(expected_words[i1:i2])
        heard_chunk = " ".join(transcript_words[j1:j2])
        if expected_chunk and heard_chunk:
            mismatches.append(f"expected \"{expected_chunk}\" but heard \"{heard_chunk}\"")
        elif expected_chunk:
            mismatches.append(f"missed \"{expected_chunk}\"")
        elif heard_chunk:
            mismatches.append(f"heard an extra \"{heard_chunk}\"")

    if not mismatches:
        return "Great pronunciation - every word matched!"
    return "Close, but not quite: " + "; ".join(mismatches) + "."
