import uuid

from app.services.recommendation import SkillCandidate, compute_skill_priority, rank_skills

SKILL_A = uuid.uuid4()
SKILL_B = uuid.uuid4()
SKILL_C = uuid.uuid4()


def _candidate(
    skill_id: uuid.UUID, *, mastery: float, review_due: bool = False, mistakes: int = 0
) -> SkillCandidate:
    return SkillCandidate(
        skill_id=skill_id,
        mastery=mastery,
        is_review_due=review_due,
        recent_incorrect_count=mistakes,
    )


def test_lower_mastery_scores_higher_priority() -> None:
    weak = _candidate(SKILL_A, mastery=10.0)
    strong = _candidate(SKILL_B, mastery=90.0)
    assert compute_skill_priority(weak) > compute_skill_priority(strong)


def test_review_due_adds_a_flat_bonus() -> None:
    due = _candidate(SKILL_A, mastery=50.0, review_due=True)
    not_due = _candidate(SKILL_B, mastery=50.0, review_due=False)
    assert compute_skill_priority(due) > compute_skill_priority(not_due)


def test_recent_mistakes_increase_priority() -> None:
    mistaken = _candidate(SKILL_A, mastery=50.0, mistakes=3)
    clean = _candidate(SKILL_B, mastery=50.0, mistakes=0)
    assert compute_skill_priority(mistaken) > compute_skill_priority(clean)


def test_rank_skills_orders_by_priority_descending() -> None:
    candidates = [
        _candidate(SKILL_A, mastery=90.0),  # low priority
        _candidate(SKILL_B, mastery=10.0),  # high priority
        _candidate(SKILL_C, mastery=50.0),  # medium priority
    ]
    ranked = rank_skills(candidates, limit=10)
    assert [c.skill_id for c in ranked] == [SKILL_B, SKILL_C, SKILL_A]


def test_rank_skills_respects_limit() -> None:
    candidates = [_candidate(uuid.uuid4(), mastery=float(i)) for i in range(10)]
    ranked = rank_skills(candidates, limit=3)
    assert len(ranked) == 3


def test_different_histories_produce_different_rankings() -> None:
    """Exit criteria: two users with different histories get different
    practice sets. This is the priority-scoring half of that guarantee."""
    user_a_candidates = [
        _candidate(SKILL_A, mastery=20.0),
        _candidate(SKILL_B, mastery=80.0),
    ]
    user_b_candidates = [
        _candidate(SKILL_A, mastery=80.0),
        _candidate(SKILL_B, mastery=20.0),
    ]

    ranked_a = [c.skill_id for c in rank_skills(user_a_candidates, limit=2)]
    ranked_b = [c.skill_id for c in rank_skills(user_b_candidates, limit=2)]

    assert ranked_a != ranked_b
    assert ranked_a == [SKILL_A, SKILL_B]
    assert ranked_b == [SKILL_B, SKILL_A]
