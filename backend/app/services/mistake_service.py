"""V3.3 Mistake Notebook: unifies three existing, previously-unsurfaced data
sources (wrong ExerciseAttempt/PracticeQuestion rows, and tutor-conversation
DetectedError rows) into one learner-facing list, plus a Type A/Type B
repeated-mistake grouping. See V3_REVISED_IMPLEMENTATION_PLAN.md §3.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.course import Exercise, ExerciseType
from app.models.evaluation import DetectedError
from app.models.practice import PracticeQuestion
from app.models.progress import ExerciseAttempt
from app.repositories import evaluation_repository, mistake_repository
from app.schemas.mistakes import (
    MistakeListOut,
    MistakeOut,
    MistakeSource,
    RepeatedMistakeGroupOut,
    RepeatedMistakeType,
)

DEFAULT_MISTAKE_PAGE_SIZE = 20
MAX_MISTAKE_PAGE_SIZE = 100

# How many recent mistakes to scan when detecting repeats (group_repeated_
# mistakes' caller). This is a summary/insight, not a paginated listing a
# learner can page arbitrarily deep into - unlike list_mistakes (which must
# stay correct for any requested page, see its docstring), a bounded recent
# window is the right, expected tradeoff here, matching this codebase's
# existing "recent" conventions (e.g. evaluation_repository.list_recent_
# errors' own limit=20 default).
REPEATED_MISTAKES_SCAN_LIMIT = 100


def _option_text(exercise: Exercise, option_id: object) -> str:
    if not isinstance(option_id, str):
        return ""
    for opt in exercise.options:
        if str(opt.id) == option_id:
            return opt.text
    return ""


def _render_submitted_text(exercise: Exercise, submitted_answer: dict) -> str:
    """submitted_answer's JSONB shape is per-type (app/services/grading.py).
    MULTIPLE_CHOICE/WORD_ORDER/MATCHING store option ids, not text - unlike
    correct_answer (already resolved to text at grading time for display),
    so this looks the ids up against the exercise's own options, same data
    FeedbackPanel.tsx would use if it rendered submitted answers historically."""
    match exercise.type:
        case ExerciseType.MULTIPLE_CHOICE:
            return _option_text(exercise, submitted_answer.get("option_id"))
        case ExerciseType.WORD_ORDER:
            ids = submitted_answer.get("option_ids")
            if not isinstance(ids, list):
                return ""
            return " ".join(_option_text(exercise, oid) for oid in ids)
        case ExerciseType.MATCHING:
            pairs = submitted_answer.get("pairs")
            if not isinstance(pairs, list):
                return ""
            rendered = []
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                left = _option_text(exercise, pair.get("left_option_id"))
                right = _option_text(exercise, pair.get("right_option_id"))
                rendered.append(f"{left} → {right}")
            return "; ".join(rendered)
        case _:
            # FILL_BLANK, TRANSLATION, LISTENING, SPEAKING, SHORT_ANSWER all
            # store the learner's literal typed/transcribed text directly.
            value = submitted_answer.get("text")
            return value if isinstance(value, str) else ""


def _render_correct_text(exercise: Exercise, correct_answer: dict) -> str | None:
    """Mirrors FeedbackPanel.tsx's CorrectAnswerSummary switch exactly - same
    per-type JSONB shapes, just rendered server-side for the Mistake
    Notebook's historical view."""
    match exercise.type:
        case ExerciseType.MULTIPLE_CHOICE:
            value = correct_answer.get("text")
            return value if isinstance(value, str) else None
        case (
            ExerciseType.FILL_BLANK
            | ExerciseType.TRANSLATION
            | ExerciseType.LISTENING
            | ExerciseType.SPEAKING
        ):
            answers = correct_answer.get("answers")
            return " / ".join(answers) if isinstance(answers, list) and answers else None
        case ExerciseType.WORD_ORDER:
            order = correct_answer.get("order")
            return " ".join(order) if isinstance(order, list) and order else None
        case ExerciseType.MATCHING:
            pairs = correct_answer.get("pairs")
            if not isinstance(pairs, list) or not pairs:
                return None
            return "; ".join(
                f"{p.get('left')} → {p.get('right')}" for p in pairs if isinstance(p, dict)
            )
        case ExerciseType.SHORT_ANSWER:
            value = correct_answer.get("corrected_answer")
            return value if isinstance(value, str) else None


def _listening_category(exercise: Exercise, correct_answer: dict) -> str | None:
    if exercise.type != ExerciseType.LISTENING:
        return None
    value = correct_answer.get("category")
    return value if isinstance(value, str) else None


def _from_exercise_attempt(row: ExerciseAttempt) -> MistakeOut:
    exercise = row.exercise
    return MistakeOut(
        id=row.id,
        source=MistakeSource.LESSON,
        skill_id=exercise.skill_id,
        skill_name=exercise.skill.name,
        exercise_id=exercise.id,
        exercise_type=exercise.type,
        prompt=exercise.prompt,
        submitted_text=_render_submitted_text(exercise, row.submitted_answer),
        correct_text=_render_correct_text(exercise, row.correct_answer),
        explanation=row.explanation,
        category=_listening_category(exercise, row.correct_answer),
        created_at=row.created_at,
    )


def _from_practice_question(row: PracticeQuestion) -> MistakeOut:
    exercise = row.exercise
    # list_wrong_practice_questions only returns answered_at IS NOT NULL,
    # is_correct=false rows, so record_answer already populated these.
    assert row.submitted_answer is not None
    assert row.answered_at is not None
    correct_answer = row.correct_answer or {}
    return MistakeOut(
        id=row.id,
        source=MistakeSource.PRACTICE,
        skill_id=exercise.skill_id,
        skill_name=exercise.skill.name,
        exercise_id=exercise.id,
        exercise_type=exercise.type,
        prompt=exercise.prompt,
        submitted_text=_render_submitted_text(exercise, row.submitted_answer),
        correct_text=_render_correct_text(exercise, correct_answer),
        explanation=row.explanation,
        category=_listening_category(exercise, correct_answer),
        created_at=row.answered_at,
    )


def _from_detected_error(row: DetectedError) -> MistakeOut:
    return MistakeOut(
        id=row.id,
        source=MistakeSource.TUTOR,
        skill_id=row.skill_id,
        skill_name=row.skill.name,
        exercise_id=None,
        exercise_type=None,
        prompt=None,
        submitted_text=row.submitted_text,
        # Honestly None, not fabricated: conversation_service._record_
        # correction never persists the AI's `corrected` field anywhere -
        # see V3_ADAPTIVE_INTELLIGENCE_AUDIT.md's finding on this exact gap.
        correct_text=None,
        explanation=row.description,
        category=None,
        created_at=row.created_at,
    )


def list_mistakes(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int = DEFAULT_MISTAKE_PAGE_SIZE,
    offset: int = 0,
    skill_id: uuid.UUID | None = None,
    source: MistakeSource | None = None,
    exercise_type: ExerciseType | None = None,
) -> MistakeListOut:
    """Merges 3 sources into one newest-first list, correct for any
    requested page depth.

    Fetches offset+limit+1 rows (not a fixed window) from each source before
    merging - for any item X, X's rank within its own source is never
    greater than X's rank in the full merged set (a source is a subset of
    the whole), so fetching each source's local top-(offset+limit+1) is
    guaranteed to include the true global top-(offset+limit+1) across all
    sources. The "+1" beyond the page itself is what makes `has_more`
    trustworthy too, at the cost of one extra row per source. This is
    O(offset) re-fetched work per request, not true cursor-based paging -
    the right tradeoff at a single learner's mistake-history scale; a
    unified SQL view or keyset pagination would be needed if that stops
    being true.

    exercise_type doesn't apply to TUTOR mistakes (they have no exercise) -
    passing it alongside source=TUTOR simply yields zero TUTOR rows, which
    is correct (a tutor mistake can never match a specific exercise type).
    """
    limit = max(1, min(limit, MAX_MISTAKE_PAGE_SIZE))
    offset = max(0, offset)
    fetch_depth = offset + limit + 1

    records: list[MistakeOut] = []

    if source is None or source == MistakeSource.LESSON:
        rows = mistake_repository.list_wrong_exercise_attempts(
            db, user_id=user_id, limit=fetch_depth, skill_id=skill_id, exercise_type=exercise_type
        )
        records.extend(_from_exercise_attempt(r) for r in rows)

    if source is None or source == MistakeSource.PRACTICE:
        rows_p = mistake_repository.list_wrong_practice_questions(
            db, user_id=user_id, limit=fetch_depth, skill_id=skill_id, exercise_type=exercise_type
        )
        records.extend(_from_practice_question(r) for r in rows_p)

    if exercise_type is None and (source is None or source == MistakeSource.TUTOR):
        rows_t = evaluation_repository.list_recent_conversation_errors(
            db, user_id=user_id, limit=fetch_depth, skill_id=skill_id
        )
        records.extend(_from_detected_error(r) for r in rows_t)

    records.sort(key=lambda r: (r.created_at, str(r.id)), reverse=True)

    page = records[offset : offset + limit]
    has_more = len(records) > offset + limit
    return MistakeListOut(items=page, limit=limit, offset=offset, has_more=has_more)


def _occasion_key(record: MistakeOut) -> uuid.UUID:
    """What counts as "one occasion" of a mistake for Type A grouping - an
    exercise_id when there is one, otherwise the mistake's own id (so two
    separate TUTOR corrections on the same skill still count as two distinct
    occasions, not one)."""
    return record.exercise_id if record.exercise_id is not None else record.id


def group_repeated_mistakes(records: list[MistakeOut]) -> list[RepeatedMistakeGroupOut]:
    """Two distinct, separately-labeled group types - never merged into one
    undifferentiated "repeated mistake" concept (V3 architecture review
    item 5): Type A (repeated difficulty - 2+ wrong attempts across
    different occasions sharing a skill) and Type B (repeated exact mistake
    - 2+ wrong attempts on the same exercise_id). A skill whose every wrong
    attempt shares one exercise_id is already fully explained by its Type B
    group and doesn't also get a Type A group for the same underlying facts.
    """
    groups: list[RepeatedMistakeGroupOut] = []

    by_exercise: dict[uuid.UUID, list[MistakeOut]] = {}
    for record in records:
        if record.exercise_id is not None:
            by_exercise.setdefault(record.exercise_id, []).append(record)
    for exercise_id, items in by_exercise.items():
        if len(items) >= 2:
            most_recent = max(items, key=lambda r: r.created_at)
            groups.append(
                RepeatedMistakeGroupOut(
                    type=RepeatedMistakeType.REPEATED_EXACT_MISTAKE,
                    skill_id=most_recent.skill_id,
                    skill_name=most_recent.skill_name,
                    exercise_id=exercise_id,
                    count=len(items),
                    most_recent=most_recent,
                )
            )

    by_skill: dict[uuid.UUID, list[MistakeOut]] = {}
    for record in records:
        by_skill.setdefault(record.skill_id, []).append(record)
    for skill_id, items in by_skill.items():
        distinct_occasions = {_occasion_key(r) for r in items}
        if len(items) >= 2 and len(distinct_occasions) >= 2:
            most_recent = max(items, key=lambda r: r.created_at)
            groups.append(
                RepeatedMistakeGroupOut(
                    type=RepeatedMistakeType.REPEATED_DIFFICULTY,
                    skill_id=skill_id,
                    skill_name=most_recent.skill_name,
                    exercise_id=None,
                    count=len(items),
                    most_recent=most_recent,
                )
            )

    groups.sort(key=lambda g: (g.count, g.most_recent.created_at), reverse=True)
    return groups


@dataclass(frozen=True)
class RepeatedMistakesSummary:
    """The lightweight count learner_insight_service's Coach context needs -
    not the full grouped listing (that's group_repeated_mistakes above,
    which mistake_service's own /me/mistakes endpoint uses directly)."""

    skills_with_repeated_difficulty: int
    exercises_with_repeated_exact_mistake: int


def get_repeated_mistakes_summary(db: Session, *, user_id: uuid.UUID) -> RepeatedMistakesSummary:
    recent = list_mistakes(db, user_id=user_id, limit=REPEATED_MISTAKES_SCAN_LIMIT, offset=0)
    groups = group_repeated_mistakes(recent.items)
    return RepeatedMistakesSummary(
        skills_with_repeated_difficulty=sum(
            1 for g in groups if g.type == RepeatedMistakeType.REPEATED_DIFFICULTY
        ),
        exercises_with_repeated_exact_mistake=sum(
            1 for g in groups if g.type == RepeatedMistakeType.REPEATED_EXACT_MISTAKE
        ),
    )
