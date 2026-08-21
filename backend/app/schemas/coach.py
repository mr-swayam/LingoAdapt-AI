"""V3.1 AI Learning Coach. Mirrors app/schemas/evaluation.py's exact Raw/
normalized split: RawCoachInsight is strict and AI-facing, CoachInsightOut
is what the rest of the app works with. See
V3_REVISED_IMPLEMENTATION_PLAN.md §1.
"""

from pydantic import BaseModel


class RawCoachInsight(BaseModel):
    """What the AI actually returns - structurally strict (rules.md: never
    trust AI output without validation)."""

    summary: str
    strengths: list[str]
    focus_areas: list[str]
    recommended_action: str
    data_note: str | None = None


class CoachInsightOut(BaseModel):
    """The normalized result the rest of the app works with. Identical shape
    to RawCoachInsight today - kept as a separate type (rather than reusing
    RawCoachInsight directly) so the AI-facing schema and the app-facing one
    can diverge later without a breaking change, matching this codebase's
    existing Raw/normalized convention (schemas/evaluation.py)."""

    summary: str
    strengths: list[str]
    focus_areas: list[str]
    recommended_action: str
    data_note: str | None = None
    # True when served from the Redis cache rather than freshly generated -
    # surfaced so the frontend can show a subtle "cached" affordance instead
    # of pretending every load is a fresh analysis.
    from_cache: bool = False

    @classmethod
    def from_raw(cls, raw: RawCoachInsight, *, from_cache: bool = False) -> "CoachInsightOut":
        return cls(
            summary=raw.summary,
            strengths=raw.strengths,
            focus_areas=raw.focus_areas,
            recommended_action=raw.recommended_action,
            data_note=raw.data_note,
            from_cache=from_cache,
        )


class InsufficientDataCoachInsight(BaseModel):
    """The deterministic, zero-AI-cost response when the learner has no
    meaningful history yet (V3.1's insufficient-data short-circuit)."""

    has_sufficient_data: bool = False
    message: str = (
        "Complete a few more learning activities so I can give you a "
        "more personalized analysis."
    )


class CoachResponseOut(BaseModel):
    """The actual GET /me/coach response shape - one schema covering both
    outcomes (rather than a FastAPI response_model union) so the frontend
    always parses one predictable shape and just branches on
    has_sufficient_data."""

    has_sufficient_data: bool
    message: str | None = None
    insight: CoachInsightOut | None = None

    @classmethod
    def from_result(
        cls, result: "CoachInsightOut | InsufficientDataCoachInsight"
    ) -> "CoachResponseOut":
        if isinstance(result, InsufficientDataCoachInsight):
            return cls(has_sufficient_data=False, message=result.message, insight=None)
        return cls(has_sufficient_data=True, message=None, insight=result)
