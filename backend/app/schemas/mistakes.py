"""V3.3 Mistake Notebook. Every field here traces to data that already
existed before V3 (ExerciseAttempt/PracticeQuestion/DetectedError) - see
V3_REVISED_IMPLEMENTATION_PLAN.md §3. No `corrected_text` for TUTOR-source
mistakes: conversation_service._record_correction never persists the AI's
`corrected` field (confirmed in the audit), so correct_text is honestly
None for that source rather than fabricated.
"""

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.course import ExerciseType


class MistakeSource(enum.StrEnum):
    LESSON = "LESSON"
    PRACTICE = "PRACTICE"
    TUTOR = "TUTOR"


class RepeatedMistakeType(enum.StrEnum):
    # Type A: 2+ wrong attempts across *different* exercises sharing a skill.
    REPEATED_DIFFICULTY = "REPEATED_DIFFICULTY"
    # Type B: 2+ wrong attempts on the *same* exercise.
    REPEATED_EXACT_MISTAKE = "REPEATED_EXACT_MISTAKE"


class MistakeOut(BaseModel):
    id: uuid.UUID
    source: MistakeSource
    skill_id: uuid.UUID
    skill_name: str
    exercise_id: uuid.UUID | None
    exercise_type: ExerciseType | None
    prompt: str | None
    submitted_text: str
    correct_text: str | None
    explanation: str | None
    category: str | None
    created_at: datetime


class MistakeListOut(BaseModel):
    items: list[MistakeOut]
    limit: int
    offset: int
    has_more: bool


class RepeatedMistakeGroupOut(BaseModel):
    type: RepeatedMistakeType
    skill_id: uuid.UUID
    skill_name: str
    exercise_id: uuid.UUID | None
    count: int
    most_recent: MistakeOut
