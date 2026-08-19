import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.analytics import AiCallLog, AiCallOperation
from app.models.course import Course, Exercise, ExerciseType, Language, Lesson, Skill, Unit
from app.models.evaluation import DetectedError, DetectedErrorSeverity, DetectedErrorType
from app.models.learner_model import LearningEvent, LearningEventType, SkillMastery
from app.models.practice import PracticeSession, PracticeSessionStatus
from app.models.progress import LessonAttempt, LessonAttemptStatus
from app.repositories import analytics_repository
from tests.auth_fixtures import create_user


def _seed_skill(db: Session, *, code: str = "TEST_SKILL") -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Returns (skill_id, exercise_id, lesson_id) for a minimal course tree -
    enough to satisfy LearningEvent/DetectedError's FK + exactly-one-source
    check, and LessonAttempt's lesson_id FK."""
    language = Language(code=f"l{uuid.uuid4().hex[:6]}", name="Test")
    db.add(language)
    db.flush()
    course = Course(language_id=language.id, title="Course", description="")
    db.add(course)
    db.flush()
    skill = Skill(course_id=course.id, code=code, name=code.title())
    db.add(skill)
    db.flush()
    unit = Unit(course_id=course.id, title="Unit", position=1)
    db.add(unit)
    db.flush()
    lesson = Lesson(unit_id=unit.id, title="Lesson", position=1)
    db.add(lesson)
    db.flush()
    exercise = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.FILL_BLANK,
        position=1,
        prompt="p",
        payload={},
        correct_answer={"answers": ["x"]},
    )
    db.add(exercise)
    db.flush()
    return skill.id, exercise.id, lesson.id


def _learning_event(
    db: Session, *, user_id: uuid.UUID, exercise_id: uuid.UUID, skill_id: uuid.UUID,
    is_correct: bool, created_at: datetime,
) -> None:
    db.add(
        LearningEvent(
            user_id=user_id,
            exercise_id=exercise_id,
            skill_id=skill_id,
            event_type=LearningEventType.ANSWER_SUBMITTED,
            is_correct=is_correct,
            difficulty=0.5,
            created_at=created_at,
        )
    )
    db.flush()


def _day_start(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


# --- Daily active users ---


def test_daily_active_user_counts(db_session: Session) -> None:
    skill_id, exercise_id, _lesson_id = _seed_skill(db_session)
    u1 = create_user(db_session, email="dau1@example.com").id
    u2 = create_user(db_session, email="dau2@example.com").id
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)

    _learning_event(
        db_session, user_id=u1, exercise_id=exercise_id, skill_id=skill_id,
        is_correct=True, created_at=_day_start(today) + timedelta(hours=1),
    )
    _learning_event(
        db_session, user_id=u2, exercise_id=exercise_id, skill_id=skill_id,
        is_correct=True, created_at=_day_start(today) + timedelta(hours=2),
    )
    _learning_event(
        db_session, user_id=u1, exercise_id=exercise_id, skill_id=skill_id,
        is_correct=False, created_at=_day_start(yesterday) + timedelta(hours=1),
    )

    counts = dict(
        analytics_repository.get_daily_active_user_counts(
            db_session, since_day=yesterday, until_day=today
        )
    )
    assert counts[today] == 2
    assert counts[yesterday] == 1


# --- Completion stats ---


def test_lesson_completion_stats(db_session: Session) -> None:
    _skill_id, _exercise_id, lesson_id = _seed_skill(db_session)
    user_id = create_user(db_session, email="lesson@example.com").id
    since = datetime.now(UTC) - timedelta(hours=1)

    db_session.add_all(
        [
            LessonAttempt(
                user_id=user_id, lesson_id=lesson_id, status=LessonAttemptStatus.COMPLETED,
                total_count=5, correct_count=5, started_at=since + timedelta(minutes=1),
            ),
            LessonAttempt(
                user_id=user_id, lesson_id=lesson_id, status=LessonAttemptStatus.IN_PROGRESS,
                total_count=5, correct_count=1, started_at=since + timedelta(minutes=2),
            ),
        ]
    )
    db_session.flush()

    started, completed = analytics_repository.get_lesson_completion_stats(db_session, since=since)
    assert started == 2
    assert completed == 1


def test_practice_completion_stats(db_session: Session) -> None:
    user_id = create_user(db_session, email="practice@example.com").id
    since = datetime.now(UTC) - timedelta(hours=1)

    db_session.add_all(
        [
            PracticeSession(
                user_id=user_id, status=PracticeSessionStatus.COMPLETED,
                total_count=5, correct_count=5, started_at=since + timedelta(minutes=1),
            ),
            PracticeSession(
                user_id=user_id, status=PracticeSessionStatus.COMPLETED,
                total_count=5, correct_count=5, started_at=since + timedelta(minutes=2),
            ),
            PracticeSession(
                user_id=user_id, status=PracticeSessionStatus.IN_PROGRESS,
                total_count=5, correct_count=0, started_at=since + timedelta(minutes=3),
            ),
        ]
    )
    db_session.flush()

    started, completed = analytics_repository.get_practice_completion_stats(
        db_session, since=since
    )
    assert started == 3
    assert completed == 2


# --- Retention ---


def test_day_n_retention(db_session: Session) -> None:
    skill_id, exercise_id, _lesson_id = _seed_skill(db_session)
    u1 = create_user(db_session, email="ret1@example.com").id
    u2 = create_user(db_session, email="ret2@example.com").id
    u3 = create_user(db_session, email="ret3@example.com").id
    today = datetime.now(UTC).date()
    week_ago = today - timedelta(days=7)

    for u in (u1, u2, u3):
        _learning_event(
            db_session, user_id=u, exercise_id=exercise_id, skill_id=skill_id,
            is_correct=True, created_at=_day_start(week_ago) + timedelta(hours=1),
        )
    for u in (u1, u2):
        _learning_event(
            db_session, user_id=u, exercise_id=exercise_id, skill_id=skill_id,
            is_correct=True, created_at=_day_start(today) + timedelta(hours=1),
        )

    cohort_size, retained = analytics_repository.get_day_n_retention(
        db_session, reference_day=today, n=7
    )
    assert cohort_size == 3
    assert retained == 2


def test_day_n_retention_empty_cohort(db_session: Session) -> None:
    cohort_size, retained = analytics_repository.get_day_n_retention(
        db_session, reference_day=datetime.now(UTC).date(), n=7
    )
    assert (cohort_size, retained) == (0, 0)


# --- AI call stats ---


def test_ai_call_stats(db_session: Session) -> None:
    since = datetime.now(UTC) - timedelta(hours=1)
    db_session.add_all(
        [
            AiCallLog(
                operation=AiCallOperation.CHAT, provider="groq", model="m", latency_ms=100,
                success=True, created_at=since + timedelta(minutes=1),
            ),
            AiCallLog(
                operation=AiCallOperation.CHAT, provider="groq", model="m", latency_ms=200,
                success=False, error_type="AITimeoutError", created_at=since + timedelta(minutes=2),
            ),
            AiCallLog(
                operation=AiCallOperation.TRANSCRIBE, provider="groq", model=None, latency_ms=50,
                success=True, created_at=since + timedelta(minutes=3),
            ),
        ]
    )
    db_session.flush()

    stats = {op: (total, failed, avg) for op, total, failed, avg in
              analytics_repository.get_ai_call_stats(db_session, since=since)}

    assert stats[AiCallOperation.CHAT] == (2, 1, 150.0)
    assert stats[AiCallOperation.TRANSCRIBE] == (1, 0, 50.0)


# --- Mistakes ---


def test_top_mistake_types(db_session: Session) -> None:
    skill_id, exercise_id, _lesson_id = _seed_skill(db_session)
    user_id = create_user(db_session, email="mistakes@example.com").id
    since = datetime.now(UTC) - timedelta(hours=1)

    def _error(error_type: DetectedErrorType) -> DetectedError:
        return DetectedError(
            user_id=user_id, exercise_id=exercise_id, skill_id=skill_id,
            error_type=error_type, severity=DetectedErrorSeverity.LOW,
            description="d", submitted_text="s", created_at=since + timedelta(minutes=1),
        )

    db_session.add_all(
        [
            _error(DetectedErrorType.GRAMMAR),
            _error(DetectedErrorType.GRAMMAR),
            _error(DetectedErrorType.SPELLING),
        ]
    )
    db_session.flush()

    top = analytics_repository.get_top_mistake_types(db_session, since=since, limit=5)
    assert top[0] == (DetectedErrorType.GRAMMAR, 2)
    assert (DetectedErrorType.SPELLING, 1) in top


# --- Weakest skills ---


def test_weakest_skills_excludes_untouched_skills(db_session: Session) -> None:
    weak_skill_id, _, _wl = _seed_skill(db_session, code="WEAK")
    strong_skill_id, _, _sl = _seed_skill(db_session, code="STRONG")
    _seed_skill(db_session, code="UNTOUCHED")  # no SkillMastery row at all
    u1 = create_user(db_session, email="weak1@example.com").id
    u2 = create_user(db_session, email="weak2@example.com").id

    db_session.add_all(
        [
            SkillMastery(
                user_id=u1, skill_id=weak_skill_id, mastery=10.0, attempt_count=3, correct_count=1
            ),
            SkillMastery(
                user_id=u2, skill_id=strong_skill_id, mastery=90.0, attempt_count=3, correct_count=3
            ),
        ]
    )
    db_session.flush()

    weakest = analytics_repository.get_weakest_skills(db_session, limit=5)
    skill_ids = [row[0] for row in weakest]

    assert skill_ids[0] == weak_skill_id
    assert strong_skill_id in skill_ids
    assert len(skill_ids) == 2  # "UNTOUCHED" excluded - no attempts recorded


# --- Improvement over time ---


def test_weekly_correctness_trend(db_session: Session) -> None:
    skill_id, exercise_id, _lesson_id = _seed_skill(db_session)
    user_id = create_user(db_session, email="trend@example.com").id
    today = datetime.now(UTC).date()
    this_monday = today - timedelta(days=today.weekday())

    # This week: 3 correct, 1 wrong.
    for is_correct in (True, True, True, False):
        _learning_event(
            db_session, user_id=user_id, exercise_id=exercise_id, skill_id=skill_id,
            is_correct=is_correct, created_at=_day_start(this_monday) + timedelta(hours=1),
        )
    # Last week: 1 correct, 1 wrong.
    last_monday = this_monday - timedelta(weeks=1)
    for is_correct in (True, False):
        _learning_event(
            db_session, user_id=user_id, exercise_id=exercise_id, skill_id=skill_id,
            is_correct=is_correct, created_at=_day_start(last_monday) + timedelta(hours=1),
        )

    trend = analytics_repository.get_weekly_correctness_trend(
        db_session, num_weeks=2, end_day=today
    )
    assert len(trend) == 2
    assert trend[0] == (last_monday, 1, 2)
    assert trend[1] == (this_monday, 3, 4)
