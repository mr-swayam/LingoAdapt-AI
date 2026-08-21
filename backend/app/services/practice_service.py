import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.models.course import Exercise, ExerciseType
from app.models.practice import PracticeQuestion, PracticeSession, PracticeSessionStatus
from app.repositories import course_repository, learner_model_repository, practice_repository
from app.services import ai_grading, learner_model_service
from app.services.grading import grade_exercise
from app.services.recommendation import SkillCandidate, rank_skills

DEFAULT_SESSION_SIZE = 5


class PracticeServiceError(Exception):
    pass


class SessionNotFoundError(PracticeServiceError):
    pass


class SessionNotOwnedError(PracticeServiceError):
    pass


class SessionAlreadyCompletedError(PracticeServiceError):
    pass


class QuestionNotInSessionError(PracticeServiceError):
    pass


def get_existing_answer(
    db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID, exercise_id: uuid.UUID
) -> PracticeQuestion | None:
    """Read-only idempotency pre-check, same rationale as
    lesson_service.get_existing_answer - lets callers that must transcribe
    audio *before* they have a submitted_answer skip that work when the
    question was already answered, rather than paying for it and having
    submit_practice_answer's own idempotency check discard the result.
    """
    session = practice_repository.get_session(db, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    if session.user_id != user_id:
        raise SessionNotOwnedError(session_id)
    question = practice_repository.get_question(db, session_id=session.id, exercise_id=exercise_id)
    if question is None or question.is_correct is None:
        return None
    return question


def _select_exercise_for_skill(
    db: Session, *, user_id: uuid.UUID, skill_id: uuid.UUID, target_difficulty: float
) -> Exercise | None:
    """Mistake review takes priority: if the learner has ever missed an
    exercise for this skill, re-serve one of those. Otherwise, adaptive
    difficulty: pick whichever exercise's static difficulty rating is
    closest to the learner's current estimated ability for this skill
    (rules.md §4).
    """
    candidates = course_repository.list_exercises_for_skill(db, skill_id)
    if not candidates:
        return None

    missed_ids = learner_model_repository.get_missed_exercise_ids(
        db, user_id=user_id, skill_id=skill_id
    )
    missed_candidates = [ex for ex in candidates if ex.id in missed_ids]
    pool = missed_candidates or candidates

    return min(pool, key=lambda ex: (abs(ex.difficulty - target_difficulty), ex.id))


def _build_candidates(db: Session, user_id: uuid.UUID, now: datetime) -> list[SkillCandidate]:
    mastery_rows = learner_model_repository.list_skill_mastery_for_user(db, user_id)
    candidates = []
    for row in mastery_rows:
        recent_incorrect = learner_model_repository.count_recent_incorrect(
            db, user_id=user_id, skill_id=row.skill_id
        )
        candidates.append(
            SkillCandidate(
                skill_id=row.skill_id,
                mastery=row.mastery,
                is_review_due=row.next_review_at is not None and row.next_review_at <= now,
                recent_incorrect_count=recent_incorrect,
            )
        )
    return candidates


def _reason_for_exercise(
    db: Session, *, user_id: uuid.UUID, exercise: Exercise, now: datetime
) -> SkillCandidate:
    """Recomputes the same real signals _build_candidates uses for
    ranking, scoped to one already-selected exercise's skill - used for
    the "why recommended" reason on a resumed (already in-progress)
    session, where the original ranking pass already happened and wasn't
    persisted (nothing here is stored/replayed from a snapshot; it's a
    fresh, current read, same as a brand-new session would compute)."""
    mastery_row = learner_model_repository.get_skill_mastery(
        db, user_id=user_id, skill_id=exercise.skill_id
    )
    mastery = mastery_row.mastery if mastery_row else 0.0
    is_review_due = bool(
        mastery_row and mastery_row.next_review_at is not None and mastery_row.next_review_at <= now
    )
    recent_incorrect = learner_model_repository.count_recent_incorrect(
        db, user_id=user_id, skill_id=exercise.skill_id
    )
    return SkillCandidate(
        skill_id=exercise.skill_id,
        mastery=mastery,
        is_review_due=is_review_due,
        recent_incorrect_count=recent_incorrect,
    )


def start_practice_session(
    db: Session, *, user_id: uuid.UUID, limit: int = DEFAULT_SESSION_SIZE
) -> tuple[PracticeSession, list[Exercise], dict[uuid.UUID, SkillCandidate]]:
    now = datetime.now(UTC)

    existing = practice_repository.get_in_progress_session(db, user_id)
    if existing is not None:
        resumed_exercises: list[Exercise] = []
        resumed_reasons: dict[uuid.UUID, SkillCandidate] = {}
        for question in existing.questions:
            exercise = course_repository.get_exercise(db, question.exercise_id)
            if exercise is None:
                continue
            resumed_exercises.append(exercise)
            resumed_reasons[exercise.id] = _reason_for_exercise(
                db, user_id=user_id, exercise=exercise, now=now
            )
        return existing, resumed_exercises, resumed_reasons

    candidates = _build_candidates(db, user_id, now)
    top_skills = rank_skills(candidates, limit=limit)

    session = practice_repository.create_session(db, user_id=user_id)
    selected_exercises: list[Exercise] = []
    reasons: dict[uuid.UUID, SkillCandidate] = {}
    for position, candidate in enumerate(top_skills, start=1):
        exercise = _select_exercise_for_skill(
            db,
            user_id=user_id,
            skill_id=candidate.skill_id,
            target_difficulty=candidate.mastery / 100.0,
        )
        if exercise is None:
            continue
        practice_repository.add_question(
            db, session_id=session.id, exercise_id=exercise.id, position=position
        )
        selected_exercises.append(exercise)
        reasons[exercise.id] = candidate

    session.total_count = len(selected_exercises)
    if session.total_count == 0:
        session.status = PracticeSessionStatus.COMPLETED
        session.completed_at = now
    db.commit()

    return session, selected_exercises, reasons


@dataclass(frozen=True)
class SubmitPracticeAnswerResult:
    is_correct: bool
    correct_answer: dict
    explanation: str | None
    session_completed: bool
    correct_count: int
    total_count: int


async def submit_practice_answer(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    exercise_id: uuid.UUID,
    submitted_answer: dict,
    ai_provider: AIProvider | None = None,
) -> SubmitPracticeAnswerResult:
    session = practice_repository.get_session(db, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    if session.user_id != user_id:
        raise SessionNotOwnedError(session_id)
    if session.status != PracticeSessionStatus.IN_PROGRESS:
        raise SessionAlreadyCompletedError(session_id)

    question = practice_repository.get_question(
        db, session_id=session.id, exercise_id=exercise_id
    )
    if question is None:
        raise QuestionNotInSessionError(exercise_id)

    exercise = course_repository.get_exercise(db, exercise_id)
    assert exercise is not None  # FK guarantees this; question can't reference a deleted exercise

    if question.is_correct is not None:
        # Idempotent resubmission: return the already-recorded result. Never
        # recompute - for SHORT_ANSWER that would mean a second paid,
        # non-deterministic AI call for the same answer.
        is_correct = question.is_correct
        correct_answer = question.correct_answer or {}
        explanation = question.explanation
    else:
        if exercise.type == ExerciseType.SHORT_ANSWER:
            submitted_text = submitted_answer.get("text", "")
            is_correct, correct_answer, explanation = await ai_grading.grade_short_answer(
                db,
                ai_provider,
                user_id=user_id,
                exercise=exercise,
                submitted_text=submitted_text,
            )
        else:
            is_correct, correct_answer = grade_exercise(exercise, submitted_answer)
            explanation = exercise.explanation

        practice_repository.record_answer(
            db,
            question=question,
            submitted_answer=submitted_answer,
            is_correct=is_correct,
            correct_answer=correct_answer,
            explanation=explanation,
            now=datetime.now(UTC),
        )
        if is_correct:
            session.correct_count += 1

        learner_model_service.record_answer_learning_event(
            db, user_id=user_id, exercise=exercise, is_correct=is_correct
        )

        answered_count = sum(1 for q in session.questions if q.is_correct is not None)
        if answered_count >= session.total_count:
            session.status = PracticeSessionStatus.COMPLETED
            session.completed_at = datetime.now(UTC)

    session_completed = session.status == PracticeSessionStatus.COMPLETED
    db.commit()

    return SubmitPracticeAnswerResult(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=explanation,
        session_completed=session_completed,
        correct_count=session.correct_count,
        total_count=session.total_count,
    )
