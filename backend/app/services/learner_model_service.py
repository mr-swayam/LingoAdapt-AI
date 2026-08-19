import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.course import Exercise
from app.models.learner_model import LearningEventType, SkillMastery
from app.repositories import learner_model_repository
from app.services import mastery, spaced_repetition

# Conversation corrections don't have a static exercise difficulty rating to
# draw on - a neutral midpoint keeps the signal in learning_events without
# implying false precision about how hard the mistake was.
CONVERSATION_MISTAKE_DIFFICULTY = 0.5


def _apply_learning_event(
    db: Session,
    *,
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    event_type: LearningEventType,
    is_correct: bool,
    difficulty: float,
    exercise_id: uuid.UUID | None = None,
    conversation_message_id: uuid.UUID | None = None,
    response_time_ms: int | None = None,
) -> SkillMastery:
    """Implements architecture.md §7's flow: event -> skill mastery update ->
    review schedule update, regardless of whether the event came from an
    exercise answer or a conversation correction.
    """
    learner_model_repository.create_learning_event(
        db,
        user_id=user_id,
        skill_id=skill_id,
        event_type=event_type,
        is_correct=is_correct,
        difficulty=difficulty,
        exercise_id=exercise_id,
        conversation_message_id=conversation_message_id,
        response_time_ms=response_time_ms,
    )

    existing = learner_model_repository.get_skill_mastery(db, user_id=user_id, skill_id=skill_id)
    old_mastery = existing.mastery if existing else 0.0
    attempt_count = (existing.attempt_count if existing else 0) + 1
    correct_count = (existing.correct_count if existing else 0) + (1 if is_correct else 0)

    now = datetime.now(UTC)
    new_mastery = mastery.compute_new_mastery(old_mastery, is_correct=is_correct)
    new_confidence = mastery.compute_confidence(attempt_count)

    schedule = spaced_repetition.compute_review_schedule(
        ease_factor=existing.ease_factor if existing else spaced_repetition.EASE_START,
        repetitions=existing.repetitions if existing else 0,
        interval_days=existing.interval_days if existing else 0,
        is_correct=is_correct,
        now=now,
    )

    return learner_model_repository.save_skill_mastery(
        db,
        user_id=user_id,
        skill_id=skill_id,
        mastery=new_mastery,
        confidence=new_confidence,
        attempt_count=attempt_count,
        correct_count=correct_count,
        last_practiced_at=now,
        next_review_at=schedule.next_review_at,
        ease_factor=schedule.ease_factor,
        repetitions=schedule.repetitions,
        interval_days=schedule.interval_days,
    )


def record_answer_learning_event(
    db: Session,
    *,
    user_id: uuid.UUID,
    exercise: Exercise,
    is_correct: bool,
    response_time_ms: int | None = None,
) -> SkillMastery:
    """Call once per fresh (non-idempotent-resubmit) exercise answer."""
    return _apply_learning_event(
        db,
        user_id=user_id,
        skill_id=exercise.skill_id,
        event_type=LearningEventType.ANSWER_SUBMITTED,
        is_correct=is_correct,
        difficulty=exercise.difficulty,
        exercise_id=exercise.id,
        response_time_ms=response_time_ms,
    )


def record_conversation_mistake(
    db: Session,
    *,
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    conversation_message_id: uuid.UUID,
) -> SkillMastery:
    """Call once per AI-flagged correction in a tutor conversation
    (rules.md §6.8). Always is_correct=False - this pathway only fires when
    the tutor actually flags a mistake, not for every utterance (rules.md
    §6.5: "correct important errors without interrupting every sentence").
    """
    return _apply_learning_event(
        db,
        user_id=user_id,
        skill_id=skill_id,
        event_type=LearningEventType.CONVERSATION_CORRECTION,
        is_correct=False,
        difficulty=CONVERSATION_MISTAKE_DIFFICULTY,
        conversation_message_id=conversation_message_id,
    )
