import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.practice import PracticeQuestion, PracticeSession, PracticeSessionStatus


def get_in_progress_session(db: Session, user_id: uuid.UUID) -> PracticeSession | None:
    stmt = (
        select(PracticeSession)
        .where(
            PracticeSession.user_id == user_id,
            PracticeSession.status == PracticeSessionStatus.IN_PROGRESS,
        )
        .options(selectinload(PracticeSession.questions))
    )
    return db.execute(stmt).scalar_one_or_none()


def get_session(db: Session, session_id: uuid.UUID) -> PracticeSession | None:
    stmt = (
        select(PracticeSession)
        .where(PracticeSession.id == session_id)
        .options(selectinload(PracticeSession.questions))
    )
    return db.execute(stmt).scalar_one_or_none()


def create_session(db: Session, *, user_id: uuid.UUID) -> PracticeSession:
    session = PracticeSession(user_id=user_id, total_count=0)
    db.add(session)
    db.flush()
    return session


def add_question(
    db: Session, *, session_id: uuid.UUID, exercise_id: uuid.UUID, position: int
) -> PracticeQuestion:
    question = PracticeQuestion(
        practice_session_id=session_id, exercise_id=exercise_id, position=position
    )
    db.add(question)
    db.flush()
    return question


def get_question(
    db: Session, *, session_id: uuid.UUID, exercise_id: uuid.UUID
) -> PracticeQuestion | None:
    stmt = select(PracticeQuestion).where(
        PracticeQuestion.practice_session_id == session_id,
        PracticeQuestion.exercise_id == exercise_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def record_answer(
    db: Session,
    *,
    question: PracticeQuestion,
    submitted_answer: dict,
    is_correct: bool,
    correct_answer: dict,
    explanation: str | None,
    now: datetime,
) -> PracticeQuestion:
    question.submitted_answer = submitted_answer
    question.is_correct = is_correct
    question.correct_answer = correct_answer
    question.explanation = explanation
    question.answered_at = now
    db.flush()
    return question
