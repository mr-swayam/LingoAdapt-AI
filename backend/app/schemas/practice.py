import uuid
from typing import Any

from pydantic import BaseModel, model_validator

from app.models.course import Exercise
from app.models.practice import PracticeSession, PracticeSessionStatus
from app.schemas.course import ExercisePublicOut
from app.services.recommendation import SkillCandidate


class PracticeReasonOut(BaseModel):
    """Real recommendation signals, not an invented explanation - the same
    fields recommendation.SkillCandidate/compute_skill_priority already use
    to rank skills, just no longer discarded before reaching the API."""

    skill_name: str
    mastery: float
    is_review_due: bool
    recent_incorrect_count: int


class PracticeStartResponse(BaseModel):
    practice_session_id: uuid.UUID
    status: PracticeSessionStatus
    total_count: int
    correct_count: int
    answered_exercise_ids: list[uuid.UUID]
    exercises: list[ExercisePublicOut]
    reasons: dict[uuid.UUID, PracticeReasonOut]

    @classmethod
    def build(
        cls,
        session: PracticeSession,
        exercises: list[Exercise],
        reasons: dict[uuid.UUID, SkillCandidate],
    ) -> "PracticeStartResponse":
        return cls(
            practice_session_id=session.id,
            status=session.status,
            total_count=session.total_count,
            correct_count=session.correct_count,
            answered_exercise_ids=[q.exercise_id for q in session.questions if q.answered_at],
            exercises=[ExercisePublicOut.from_model(ex) for ex in exercises],
            reasons={
                ex.id: PracticeReasonOut(
                    skill_name=ex.skill.name,
                    mastery=round(reasons[ex.id].mastery, 1),
                    is_review_due=reasons[ex.id].is_review_due,
                    recent_incorrect_count=reasons[ex.id].recent_incorrect_count,
                )
                for ex in exercises
                if ex.id in reasons
            },
        )


class PracticeAgainRequest(BaseModel):
    """V3.3 "Practice Again" - exactly one of the two, matching the two
    honestly-distinct actions the Mistake Notebook offers: `skill_id`
    ("Practice this skill again", offered on a repeated-difficulty group)
    or `exercise_id` ("Retry this exercise", offered on a repeated-exact-
    mistake group or any single mistake card)."""

    skill_id: uuid.UUID | None = None
    exercise_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "PracticeAgainRequest":
        if (self.skill_id is None) == (self.exercise_id is None):
            raise ValueError("Provide exactly one of skill_id or exercise_id")
        return self


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
