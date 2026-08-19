"""Deterministic, server-side grading for every exercise type except
SHORT_ANSWER (app/services/ai_grading.py).

No AI *judgment* involved: every exercise type here has an objectively
correct answer, so grading is plain equality/similarity logic per rules.md
("Use deterministic code... Use AI for language understanding"). SPEAKING
is graded here too - its transcript comes from an AI speech-to-text call,
but the correctness decision itself is a deterministic string comparison,
not an AI opinion.
"""

import uuid

from app.models.course import Exercise, ExerciseOption, ExerciseType
from app.services import pronunciation


class GradingError(ValueError):
    """Raised when submitted_answer doesn't match the shape this exercise type expects."""


def grade_exercise(exercise: Exercise, submitted_answer: dict) -> tuple[bool, dict]:
    """Returns (is_correct, correct_answer_for_display)."""
    match exercise.type:
        case ExerciseType.MULTIPLE_CHOICE:
            return _grade_multiple_choice(exercise, submitted_answer)
        case ExerciseType.FILL_BLANK | ExerciseType.TRANSLATION | ExerciseType.LISTENING:
            return _grade_text(exercise, submitted_answer)
        case ExerciseType.WORD_ORDER:
            return _grade_word_order(exercise, submitted_answer)
        case ExerciseType.MATCHING:
            return _grade_matching(exercise, submitted_answer)
        case ExerciseType.SPEAKING:
            return _grade_speaking(exercise, submitted_answer)
        case ExerciseType.SHORT_ANSWER:
            # Free-form answers are graded by app/services/ai_grading.py,
            # dispatched before this function is ever called - reaching
            # here means a caller forgot to branch on exercise.type.
            raise GradingError(
                "SHORT_ANSWER exercises must be graded via ai_grading.grade_short_answer, "
                "not grade_exercise"
            )


def _parse_uuid(value: object, field: str) -> uuid.UUID:
    if not isinstance(value, str):
        raise GradingError(f"'{field}' must be a string UUID")
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise GradingError(f"'{field}' is not a valid UUID") from exc


def _grade_multiple_choice(exercise: Exercise, submitted_answer: dict) -> tuple[bool, dict]:
    if "option_id" not in submitted_answer:
        raise GradingError("MULTIPLE_CHOICE answer requires 'option_id'")
    option_id = _parse_uuid(submitted_answer["option_id"], "option_id")

    options_by_id = {opt.id: opt for opt in exercise.options}
    submitted_option = options_by_id.get(option_id)
    if submitted_option is None:
        raise GradingError("option_id does not belong to this exercise")

    correct_option = next(opt for opt in exercise.options if opt.is_correct)
    is_correct = bool(submitted_option.is_correct)
    return is_correct, {"option_id": str(correct_option.id), "text": correct_option.text}


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _grade_text(exercise: Exercise, submitted_answer: dict) -> tuple[bool, dict]:
    if "text" not in submitted_answer or not isinstance(submitted_answer["text"], str):
        raise GradingError("this exercise requires a string 'text' answer")

    accepted_answers: list[str] = exercise.correct_answer.get("answers", [])
    submitted_normalized = _normalize_text(submitted_answer["text"])
    is_correct = any(_normalize_text(ans) == submitted_normalized for ans in accepted_answers)
    return is_correct, {"answers": accepted_answers}


def _grade_word_order(exercise: Exercise, submitted_answer: dict) -> tuple[bool, dict]:
    if "option_ids" not in submitted_answer or not isinstance(
        submitted_answer["option_ids"], list
    ):
        raise GradingError("WORD_ORDER answer requires a list 'option_ids'")

    options_by_id = {opt.id: opt for opt in exercise.options}
    submitted_ids = [_parse_uuid(raw, "option_ids[]") for raw in submitted_answer["option_ids"]]

    if any(oid not in options_by_id for oid in submitted_ids):
        raise GradingError("option_ids contains an id that does not belong to this exercise")

    correct_options = sorted(exercise.options, key=lambda o: o.correct_position or 0)
    correct_ids = [opt.id for opt in correct_options]

    is_correct = submitted_ids == correct_ids
    return is_correct, {"order": [opt.text for opt in correct_options]}


def _grade_matching(exercise: Exercise, submitted_answer: dict) -> tuple[bool, dict]:
    if "pairs" not in submitted_answer or not isinstance(submitted_answer["pairs"], list):
        raise GradingError("MATCHING answer requires a list 'pairs'")

    options_by_id: dict[uuid.UUID, ExerciseOption] = {opt.id: opt for opt in exercise.options}
    left_options = [opt for opt in exercise.options if opt.match_group == "left"]
    right_by_key = {opt.match_key: opt for opt in exercise.options if opt.match_group == "right"}

    submitted_pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    for raw_pair in submitted_answer["pairs"]:
        if not isinstance(raw_pair, dict) or "left_option_id" not in raw_pair or (
            "right_option_id" not in raw_pair
        ):
            raise GradingError("each pair requires 'left_option_id' and 'right_option_id'")
        left_id = _parse_uuid(raw_pair["left_option_id"], "left_option_id")
        right_id = _parse_uuid(raw_pair["right_option_id"], "right_option_id")
        if left_id not in options_by_id or right_id not in options_by_id:
            raise GradingError("pair references an option that does not belong to this exercise")
        submitted_pairs.append((left_id, right_id))

    submitted_by_left = dict(submitted_pairs)
    is_correct = len(submitted_pairs) == len(left_options) and all(
        options_by_id[left_id].match_key == options_by_id[right_id].match_key
        for left_id, right_id in submitted_pairs
    ) and len(submitted_by_left) == len(left_options)

    correct_answer = {
        "pairs": [
            {"left": left.text, "right": right_by_key[left.match_key].text}
            for left in left_options
        ]
    }
    return is_correct, correct_answer


def _grade_speaking(exercise: Exercise, submitted_answer: dict) -> tuple[bool, dict]:
    """submitted_answer['text'] is a transcript already produced by
    app.services.speech_service.transcribe_audio at the API boundary -
    grading itself never touches audio or calls the AI provider directly."""
    if "text" not in submitted_answer or not isinstance(submitted_answer["text"], str):
        raise GradingError("SPEAKING answer requires a string 'text' transcript")

    transcript = submitted_answer["text"]
    accepted_answers: list[str] = exercise.correct_answer.get("answers", [])

    best_answer = max(
        accepted_answers,
        key=lambda ans: pronunciation.similarity_ratio(ans, transcript),
        default="",
    )
    is_correct = pronunciation.is_close_enough(best_answer, transcript) if best_answer else False

    return is_correct, {
        "answers": accepted_answers,
        "transcript": transcript,
        "feedback": pronunciation.describe_difference(best_answer, transcript)
        if best_answer
        else "",
    }
