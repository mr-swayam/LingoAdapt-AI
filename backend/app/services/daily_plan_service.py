"""V3.2 Personalized Daily Plan - generated fresh on every request from live
data, never persisted (no `daily_plans` table). See
V3_REVISED_IMPLEMENTATION_PLAN.md §2.

Completion boundary (V3 architecture review item 1): the plan is
regenerated on every GET, so a task's "done" state can never be computed
relative to the current request's own timestamp (that reference point
moves forward on every call, so nothing would ever stay "done"). Every
task type is instead checked against a stable, live condition:
  - REVIEW: done once its skill no longer appears in list_due_for_review.
    A task here is, by construction, never already-done - if it were, it
    wouldn't have been selected into the list in the first place, so it
    simply stops appearing once reviewed rather than lingering "checked
    off".
  - LESSON: done once that lesson's `completed` flag is true - same
    reasoning: an already-completed lesson is never selected as "the next
    incomplete lesson" to begin with.
  - PRACTICE: done once SkillMastery.last_practiced_at falls on-or-after
    the start of "today". Unlike REVIEW/LESSON, a practiced skill can still
    legitimately remain a top-ranked PRACTICE candidate (its mastery may
    still be relatively low even after one round), so this is the one task
    type where a visible, real completed=True is actually observable.

Local day, not server UTC day (V3 architecture review item 13): this app
stores no per-user timezone anywhere (confirmed by grep across
app/models during the architecture review). get_daily_plan accepts an
optional `local_date`, computed client-side from the learner's actual
browser-local date; when absent, it falls back to server UTC-today. No
timezone is stored anywhere - this is a stateless per-request hint, not new
persistence.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models.course import Lesson
from app.repositories import course_repository, gamification_repository, learner_model_repository
from app.schemas.daily_plan import DailyPlanOut, DailyPlanTaskOut, TaskType
from app.schemas.practice import PracticeReasonOut
from app.services import practice_service
from app.services.recommendation import rank_skills

DEFAULT_PLAN_SIZE = 5


def _day_start_utc(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


def _find_next_incomplete_lesson(db: Session, *, user_id: uuid.UUID) -> Lesson | None:
    """First lesson (in course/unit/lesson position order) this learner
    hasn't completed - reuses the exact same completion data CourseDetailOut
    already surfaces on the /learn page (gamification_repository.
    get_completed_lesson_ids), not a separate notion of "done"."""
    courses = course_repository.list_published_courses(db)
    all_lesson_ids = [
        lesson.id for course in courses for unit in course.units for lesson in unit.lessons
    ]
    completed_ids = gamification_repository.get_completed_lesson_ids(db, user_id, all_lesson_ids)
    for course in courses:
        for unit in course.units:
            for lesson in unit.lessons:
                if lesson.id not in completed_ids:
                    return lesson
    return None


def get_daily_plan(
    db: Session, *, user_id: uuid.UUID, local_date: date | None = None
) -> DailyPlanOut:
    now = datetime.now(UTC)
    plan_date = local_date if local_date is not None else now.date()
    day_start = _day_start_utc(plan_date)

    tasks: list[DailyPlanTaskOut] = []
    covered_skill_ids: set[uuid.UUID] = set()

    # 1. REVIEW - highest priority.
    review_rows = learner_model_repository.list_due_for_review(db, user_id=user_id, now=now)
    for row in review_rows:
        recent_incorrect = learner_model_repository.count_recent_incorrect(
            db, user_id=user_id, skill_id=row.skill_id
        )
        tasks.append(
            DailyPlanTaskOut(
                task_type=TaskType.REVIEW,
                skill_id=row.skill_id,
                skill_name=row.skill.name,
                reason=PracticeReasonOut(
                    skill_name=row.skill.name,
                    mastery=round(row.mastery, 1),
                    is_review_due=True,
                    recent_incorrect_count=recent_incorrect,
                ),
                completed=False,
            )
        )
        covered_skill_ids.add(row.skill_id)

    # 2. PRACTICE - weak skills via the exact existing recommendation
    # engine (recommendation.rank_skills, via practice_service.
    # build_skill_candidates - not a reimplementation), skipping any skill
    # already covered by a REVIEW task above so the same skill never
    # produces two tasks in one plan.
    candidates = practice_service.build_skill_candidates(db, user_id, now)
    ranked = rank_skills(candidates, limit=DEFAULT_PLAN_SIZE)
    for candidate in ranked:
        if candidate.skill_id in covered_skill_ids:
            continue
        skill = course_repository.get_skill(db, candidate.skill_id)
        if skill is None:
            continue
        mastery_row = learner_model_repository.get_skill_mastery(
            db, user_id=user_id, skill_id=candidate.skill_id
        )
        completed = bool(
            mastery_row
            and mastery_row.last_practiced_at is not None
            and mastery_row.last_practiced_at >= day_start
        )
        tasks.append(
            DailyPlanTaskOut(
                task_type=TaskType.PRACTICE,
                skill_id=candidate.skill_id,
                skill_name=skill.name,
                reason=PracticeReasonOut(
                    skill_name=skill.name,
                    mastery=round(candidate.mastery, 1),
                    is_review_due=candidate.is_review_due,
                    recent_incorrect_count=candidate.recent_incorrect_count,
                ),
                completed=completed,
            )
        )
        covered_skill_ids.add(candidate.skill_id)

    # 3. LESSON - one "continue learning" task, never fabricated when every
    # lesson is already complete (or no course exists at all).
    next_lesson = _find_next_incomplete_lesson(db, user_id=user_id)
    if next_lesson is not None:
        tasks.append(
            DailyPlanTaskOut(
                task_type=TaskType.LESSON,
                lesson_id=next_lesson.id,
                lesson_title=next_lesson.title,
                reason=None,
                completed=False,
            )
        )

    return DailyPlanOut(tasks=tasks, generated_for_date=plan_date.isoformat())
