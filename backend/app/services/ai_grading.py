"""Bridges AI-evaluated free-form answers into the same
(is_correct, correct_answer, explanation) shape app/services/grading.py
produces for deterministic types, so lesson_service/practice_service don't
need to know which kind of grading happened.
"""

import uuid

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.exceptions import AIProviderNotConfiguredError
from app.models.course import Exercise
from app.models.evaluation import DetectedErrorSeverity, DetectedErrorType
from app.repositories import evaluation_repository
from app.services.evaluation_service import evaluate_free_response
from app.services.grading import GradingError

# rules.md §2.10: never trust AI output without validation. score >= this
# threshold counts as "correct" for mastery/streak purposes - the AI's own
# is_correct flag is the primary signal, but a numeric floor guards against
# a borderline case where the model sets is_correct=true with a low score.
CORRECT_SCORE_THRESHOLD = 0.6

# Phase 12 AI cost control: nothing capped submitted_text's length before it
# was interpolated into a paid Groq prompt (app/schemas/course.py's
# AnswerSubmitRequest.submitted_answer is an untyped dict) - a learner (or
# anything replaying the API) could otherwise submit an arbitrarily large
# string per answer. Matches the cap already on tutor conversation turns
# (app/schemas/conversation.py's SendMessageRequest.text).
MAX_SUBMITTED_TEXT_LENGTH = 2000

async def grade_short_answer(
    db: Session,
    provider: AIProvider | None,
    *,
    user_id: uuid.UUID,
    exercise: Exercise,
    submitted_text: str,
) -> tuple[bool, dict, str | None]:
    if provider is None:
        raise AIProviderNotConfiguredError
    if len(submitted_text) > MAX_SUBMITTED_TEXT_LENGTH:
        raise GradingError(
            f"Answer is too long (max {MAX_SUBMITTED_TEXT_LENGTH} characters)."
        )

    # AIProviderError propagates as-is - the caller must not record any
    # state on failure (project_requirement_document.md §13: "AI failure
    # must not corrupt learning state").
    result = await evaluate_free_response(
        provider,
        prompt=exercise.prompt,
        model_answer=exercise.correct_answer.get("model_answer", ""),
        rubric=exercise.correct_answer.get("rubric", ""),
        submitted_text=submitted_text,
    )

    is_correct = result.is_correct and result.score >= CORRECT_SCORE_THRESHOLD

    for error in result.errors:
        # schemas.evaluation.{ErrorType,ErrorSeverity} and
        # models.evaluation.{DetectedErrorType,DetectedErrorSeverity} are
        # separate enum classes with matching string values - the schema
        # layer shouldn't depend on the persistence layer's enums, so
        # convert explicitly by value rather than importing across layers.
        evaluation_repository.record_detected_error(
            db,
            user_id=user_id,
            exercise_id=exercise.id,
            skill_id=exercise.skill_id,
            error_type=DetectedErrorType(error.type.value),
            severity=DetectedErrorSeverity(error.severity.value),
            description=error.skill,
            submitted_text=submitted_text,
        )

    correct_answer = {"corrected_answer": result.corrected_answer, "score": result.score}
    return is_correct, correct_answer, result.explanation
