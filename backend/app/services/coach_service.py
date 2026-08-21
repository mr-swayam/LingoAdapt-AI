"""V3.1 AI Learning Coach. Follows evaluation_service.py's exact pattern:
strict system prompt -> json_mode chat call -> json.loads + Raw schema
validation in one try/except -> AIResponseValidationError on failure, never
a retry or a fabricated fallback. See V3_REVISED_IMPLEMENTATION_PLAN.md §1.
"""

import json
import logging
import uuid

import redis
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, ChatMessage
from app.ai.exceptions import AIProviderNotConfiguredError, AIResponseValidationError
from app.core.rate_limit import get_redis_client
from app.schemas.coach import CoachInsightOut, InsufficientDataCoachInsight, RawCoachInsight
from app.services import learner_insight_service

logger = logging.getLogger("app.ai")

COACH_CACHE_KEY_PREFIX = "coach_insight:"
# "On the order of hours" per the plan: long enough that opening the Coach
# page repeatedly in one sitting doesn't regenerate every time (each
# regeneration is a real, metered AI call), short enough that day-to-day
# staleness is bounded even without an activity-triggered invalidation firing.
COACH_CACHE_TTL_SECONDS = 6 * 60 * 60

SYSTEM_PROMPT = """You are an AI learning coach for a language-learning app. You will be given \
JSON data with two sections: "observed_facts" (direct, measured facts about this learner) and \
"calculated_trends" (deterministic computations already performed on those facts). \
Respond with ONLY a single JSON object (no markdown, no backticks, no text outside the JSON) \
matching exactly this shape:

{
  "summary": "2-3 sentence grounded summary of the learner's current state",
  "strengths": ["short phrase", "..."],
  "focus_areas": ["short phrase", "..."],
  "recommended_action": "one specific, encouraging suggestion for what to do next",
  "data_note": "a short note if the data is thin or a caveat applies, otherwise null"
}

Strict rules:
- "summary", "strengths", and "focus_areas" must be grounded restatements of the supplied \
observed_facts and calculated_trends ONLY. Never introduce a statistic, skill name, or event \
that is not present in the supplied data.
- "recommended_action" is the one field where you may synthesize a genuine suggestion, but it \
must still be grounded in the supplied data (e.g. suggest reviewing a skill actually listed as \
weak or due for review) - never invent a skill or activity absent from the data.
- Do not diagnose language ability beyond what the data shows. Do not fabricate encouragement \
about progress that is not reflected in the data.
- Be encouraging, concise, and specific."""


def _cache_key(user_id: uuid.UUID) -> str:
    return f"{COACH_CACHE_KEY_PREFIX}{user_id}"


def _read_cache(client: redis.Redis, user_id: uuid.UUID) -> CoachInsightOut | None:
    try:
        raw = client.get(_cache_key(user_id))
    except redis.RedisError:
        logger.warning("coach_cache_read_unavailable user_id=%s", user_id)
        return None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        return CoachInsightOut.model_validate({**data, "from_cache": True})
    except (json.JSONDecodeError, ValidationError):
        logger.warning("coach_cache_content_invalid user_id=%s", user_id)
        return None


def _write_cache(client: redis.Redis, user_id: uuid.UUID, insight: CoachInsightOut) -> None:
    try:
        client.set(_cache_key(user_id), insight.model_dump_json(), ex=COACH_CACHE_TTL_SECONDS)
    except redis.RedisError:
        logger.warning("coach_cache_write_unavailable user_id=%s", user_id)


def invalidate_coach_cache(user_id: uuid.UUID, *, redis_client: redis.Redis | None = None) -> None:
    """Called at the two "real completion" checkpoints this app already
    treats as meaningful (a lesson or practice session reaching COMPLETED -
    see lesson_service.submit_answer / practice_service.submit_practice_
    answer) so the next Coach fetch after finishing one regenerates instead
    of serving a now-stale insight (V3 architecture review item 14).
    Deliberately not invoked per single exercise answer - that would defeat
    the cache's purpose mid-session. Fails open exactly like check_rate_
    limit: a Redis outage must never fail the calling request over a cache
    invalidation."""
    client = redis_client if redis_client is not None else get_redis_client()
    try:
        client.delete(_cache_key(user_id))
    except redis.RedisError:
        logger.warning("coach_cache_invalidate_unavailable user_id=%s", user_id)


def _build_context(db: Session, user_id: uuid.UUID) -> dict:
    """Explicitly split into observed_facts (direct reads) and calculated_
    trends (deterministic computations over those facts) - V3 architecture
    review item 3. Only keys with real backing data are included; an empty
    improving_skills/repeated_mistakes result is omitted entirely rather
    than sent as an empty list for the model to weigh."""
    weak_skills = learner_insight_service.get_weak_skills(db, user_id=user_id)
    improving_skills = learner_insight_service.get_improving_skills(db, user_id=user_id)
    review_priorities = learner_insight_service.get_review_priorities(db, user_id=user_id)
    activity = learner_insight_service.get_recent_activity_summary(db, user_id=user_id)
    mistakes = learner_insight_service.get_repeated_mistakes_summary(db, user_id=user_id)

    observed_facts: dict = {
        "weakest_skills": [
            {
                "skill_name": s.skill_name,
                "mastery_percent": round(s.mastery, 1),
                "attempt_count": s.attempt_count,
            }
            for s in weak_skills
        ],
        "recent_activity": {
            "lessons_completed_last_30_days": activity.lesson_completion.completed,
            "practice_sessions_completed_last_30_days": activity.practice_completion.completed,
        },
    }
    if review_priorities:
        observed_facts["skills_due_for_review"] = [r.skill_name for r in review_priorities]

    calculated_trends: dict = {}
    if improving_skills:
        calculated_trends["improving_skills"] = [
            {
                "skill_name": s.skill_name,
                "recent_accuracy_percent": round(s.recent_accuracy, 0),
                "previous_accuracy_percent": round(s.previous_accuracy, 0),
            }
            for s in improving_skills
        ]
    if mistakes.skills_with_repeated_difficulty or mistakes.exercises_with_repeated_exact_mistake:
        calculated_trends["repeated_mistakes"] = {
            "skills_with_repeated_difficulty": mistakes.skills_with_repeated_difficulty,
            "exercises_with_repeated_exact_mistake": mistakes.exercises_with_repeated_exact_mistake,
        }

    context: dict = {"observed_facts": observed_facts}
    if calculated_trends:
        context["calculated_trends"] = calculated_trends
    return context


async def get_coach_insight(
    db: Session,
    *,
    user_id: uuid.UUID,
    ai_provider: AIProvider | None,
    force_refresh: bool = False,
    redis_client: redis.Redis | None = None,
) -> CoachInsightOut | InsufficientDataCoachInsight:
    client = redis_client if redis_client is not None else get_redis_client()

    if force_refresh:
        try:
            client.delete(_cache_key(user_id))
        except redis.RedisError:
            logger.warning("coach_cache_invalidate_unavailable user_id=%s", user_id)
    else:
        cached = _read_cache(client, user_id)
        if cached is not None:
            return cached

    if not learner_insight_service.has_any_learning_history(db, user_id=user_id):
        # Zero AI cost, zero hallucination risk - matches the spec's exact
        # example message. Deliberately never cached: this is a cheap DB
        # read, not an AI call, so there's nothing expensive to save by
        # caching it, and caching it would risk it outliving the moment the
        # learner's very next answer makes it no longer true.
        return InsufficientDataCoachInsight()

    if ai_provider is None:
        raise AIProviderNotConfiguredError

    context = _build_context(db, user_id)
    response = await ai_provider.chat(
        [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=json.dumps(context)),
        ],
        json_mode=True,
        max_tokens=600,
        temperature=0.3,
    )

    try:
        raw_data = json.loads(response.content)
        raw = RawCoachInsight.model_validate(raw_data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("coach_insight_schema_invalid content=%r error=%s", response.content, exc)
        raise AIResponseValidationError(
            f"AI coach response failed schema validation: {exc}"
        ) from exc

    insight = CoachInsightOut.from_raw(raw)
    _write_cache(client, user_id, insight)
    return insight
