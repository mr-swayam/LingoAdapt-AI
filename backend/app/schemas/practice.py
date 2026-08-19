import uuid
from typing import Any

from pydantic import BaseModel

from app.models.course import Exercise
from app.models.practice import PracticeSession, PracticeSessionStatus
from app.schemas.course import ExercisePublicOut


class PracticeStartResponse(BaseModel):
    practice_session_id: uuid.UUID
    status: PracticeSessionStatus
    total_count: int
    correct_count: int
    answered_exercise_ids: list[uuid.UUID]
    exercises: list[ExercisePublicOut]

    @classmethod
    def build(
        cls, session: PracticeSession, exercises: list[Exercise]
    ) -> "PracticeStartResponse":
        return cls(
            practice_session_id=session.id,
            status=session.status,
            total_count=session.total_count,
            correct_count=session.correct_count,
            answered_exercise_ids=[q.exercise_id for q in session.questions if q.answered_at],
            exercises=[ExercisePublicOut.from_model(ex) for ex in exercises],
        )


class PracticeAnswerRequest(BaseModel):
    exercise_id: uuid.UUID
    submitted_answer: dict[str, Any]


class PracticeAnswerResult(BaseModel):
    is_correct: bool
    correct_answer: dict[str, Any]
    explanation: str | None
    session_completed: bool
    correct_count: int
    total_count: int


class PracticeAudioAnswerResult(PracticeAnswerResult):
    """Same shape as PracticeAnswerResult, plus the AI-transcribed text
    (Phase 8 SPEAKING exercises)."""

    transcript: str
