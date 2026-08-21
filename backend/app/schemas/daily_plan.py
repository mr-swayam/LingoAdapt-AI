"""V3.2 Personalized Daily Plan. TaskType is Python-level only (the plan is
never persisted - no `daily_plans` table), placed here rather than in
app/models/ because every enum that lives there today backs a real
`Enum(..., native_enum=True)` database column (ExerciseType,
PracticeSessionStatus, DetectedErrorType, ...); TaskType has no column to
back, so it belongs with the other purely-schema/service-level enum in this
codebase (MistakeSource, schemas/mistakes.py), not models/.
"""

import enum
import uuid

from pydantic import BaseModel

from app.schemas.practice import PracticeReasonOut


class TaskType(enum.StrEnum):
    """Exactly the members backed by a real recommendation signal today
    (V3 architecture review item 2) - not LISTENING/SPEAKING/CONVERSATION/
    WRITING, since no genuine per-type signal exists yet (confirmed in
    V3_ADAPTIVE_INTELLIGENCE_AUDIT.md §4.4). daily_plan_service.get_daily_
    plan evaluates each supported type in turn and emits a task only when
    its real condition is met, so adding a future type is a small additive
    change to that evaluation, not a redesign."""

    REVIEW = "REVIEW"
    PRACTICE = "PRACTICE"
    LESSON = "LESSON"


class DailyPlanTaskOut(BaseModel):
    task_type: TaskType
    skill_id: uuid.UUID | None = None
    skill_name: str | None = None
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    # Real recommendation signals (same PracticeReasonOut shape the Practice
    # page already surfaces) - None for LESSON tasks, which have no skill-
    # priority score behind them.
    reason: PracticeReasonOut | None = None
    completed: bool


class DailyPlanOut(BaseModel):
    tasks: list[DailyPlanTaskOut]
    # The calendar day this plan's completion checks were evaluated against
    # (the caller's local_date if supplied, otherwise server UTC-today) -
    # lets the frontend confirm which "day" a plan reflects.
    generated_for_date: str
