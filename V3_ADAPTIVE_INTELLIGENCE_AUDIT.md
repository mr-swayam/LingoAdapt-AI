# V3 Adaptive Intelligence Audit — AI Language Learning Tutor

**Status: audit only. No implementation has occurred. This document is the required first deliverable, per the explicit instruction to stop after the audit and await approval.**

Every claim below was produced by either (a) actually running the corresponding command in this environment, or (b) reading the actual current file contents directly (not from memory of earlier phases without re-verification). Where something could not be confirmed, it's marked as such rather than assumed.

---

## 0. Documentation check

All 11 referenced files exist in the repo root:

`project_requirement_document.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, `memory.md`, `README.md`, `RELEASE_CANDIDATE_REPORT.md`, `V2_1_UI_REDESIGN_REPORT.md`, `V2_PREMIUM_UI_AUDIT.md`, `V2_PREMIUM_UI_REPORT.md` — confirmed present via direct filesystem check, not assumed.

**One finding worth flagging**: `README.md`'s "Current status" section still reads *"Phase 12 — Production Hardening is complete... the final phase"* — it was never updated to reflect Phase 13 (Release Candidate), Phase 14 (Production Deployment), V2.1 (Audio Learning Features), or the V2 Premium UI Redesign, all of which are real, completed, previously-reported work. `README.md` is stale for the "current status" line specifically; the phase-by-phase historical notes further down remain accurate for what they document. Not fixed as part of this audit (out of scope), but noted so it isn't mistaken for the actual current state.

## 1. Actual baseline (re-run in this session, not assumed from history)

| Check | Result |
|---|---|
| Backend `pytest -q` | **322 passed**, 0 failed |
| Backend `ruff check .` | Clean |
| Backend `mypy app` | Clean (96 source files) |
| Frontend `vitest run` | **70 passed** (14 test files), 0 failed |
| Frontend `eslint .` | Clean |
| Frontend `tsc --noEmit` | Clean |
| Frontend `next build` | Succeeds, 16 routes, all URLs unchanged |

These numbers match the historical baseline claimed at the start of this task — confirmed by actually running everything in this session, not carried forward from memory.

---

## 2. Repository inspection summary

Inspected directly and via three focused research passes: `backend/app/models/*` (learner_model, progress, practice, evaluation, conversation, analytics), `backend/app/repositories/*` (learner_model, evaluation, analytics, progress by inference), `backend/app/services/*` (mastery, spaced_repetition, recommendation, practice_service, learner_model_service, evaluation_service, ai_grading, conversation_ai, conversation_service, listening_evaluation, grading, analytics_service), `backend/app/api/deps.py`, `backend/app/core/rate_limit.py`, `backend/app/ai/*` (base, groq_provider, metering, exceptions, factory), `backend/app/core/config.py`, `backend/app/core/logging_config.py`, `backend/app/core/middleware.py`. Frontend architecture (shell, design system, page structure) was already established in `V2_PREMIUM_UI_AUDIT.md`/`V2_PREMIUM_UI_REPORT.md` from the immediately prior phase and was not re-audited here since nothing in this session has changed it.

---

## 4.1 Existing Learner Intelligence

**Learner model** (`app/models/learner_model.py`):
- `LearningEvent` — append-only, never mutated. Columns: `user_id`, `exercise_id` (nullable), `conversation_message_id` (nullable, exactly one of the two set, enforced by a CHECK constraint), `skill_id`, `event_type` (`ANSWER_SUBMITTED` or `CONVERSATION_CORRECTION` — only two members exist), `is_correct` (bool), `difficulty` (float), `response_time_ms` (nullable, **not currently populated by any frontend code** — the column exists but nothing writes a non-null value into it), `created_at` (indexed). **Does not store the submitted answer or the correct answer** — only whether it was right, how hard it was, and when.
- `SkillMastery` — one row per `(user_id, skill_id)`, **updated in place, no history retained**. `mastery` (0–100, bounded by DB CHECK), `confidence` (0–100), `attempt_count`, `correct_count`, `last_practiced_at`, `next_review_at`, plus SM-2-style `ease_factor`/`repetitions`/`interval_days`.

**Mastery logic** (`app/services/mastery.py`): EMA — `new_mastery = old_mastery * 0.92 + (100 if correct else 0) * 0.08`, clamped [0,100]. `confidence = min(100, attempt_count / 10 * 100)`.

**Review scheduling** (`app/services/spaced_repetition.py`): simplified SM-2. Incorrect → ease −0.2 (floor 1.3), repetitions reset to 0, next review in 1 day. Correct → ease +0.1, repetitions+1, interval 1/3/`round(interval*ease)` days for reps 1/2/3+, capped at 365 days.

**Recommendation logic** (`app/services/recommendation.py`): `SkillCandidate(skill_id, mastery, is_review_due, recent_incorrect_count)`. `compute_skill_priority = (100 - mastery) + (50 if review_due else 0) + (recent_incorrect_count * 15)`. `rank_skills` sorts descending, truncates to a limit. Pure, deterministic, no AI, no DB access — a clean function to reuse as-is.

**Practice recommendation reasoning** (`app/services/practice_service.py`, added earlier this session): `start_practice_session` already returns, per exercise, the exact `SkillCandidate` that justified picking it — surfaced to the API today as `PracticeReasonOut {skill_name, mastery, is_review_due, recent_incorrect_count}`. This is the **existing "why recommended" building block** — not a free-text explanation, a structured, real-data object. `_reason_for_exercise` recomputes this live (not from a stale snapshot) even for a resumed session.

**Existing analytics** (`app/services/analytics_service.py`, `app/repositories/analytics_repository.py`): per-user `get_learner_activity` (lesson/practice completion stats, 8-week accuracy trend from `LearningEvent`) and platform-wide `get_overview` (admin dashboard) both exist and work, added across this session's earlier phases.

**Per-attempt answer data** (the most important finding for V3.3, detailed in §4.5): `ExerciseAttempt` (lesson exercises) and `PracticeQuestion` (practice exercises) **both already store the learner's literal submitted answer (JSONB), the correct answer (JSONB), `is_correct`, and a timestamp**, per attempt. This is real, structured, historical mistake data that already exists — it has simply never been queried for a learner-facing "show me my mistakes" view.

**AI Tutor corrections** (`app/services/conversation_ai.py`, `app/services/conversation_service.py`): the AI's four correction fields per turn are `original`, `corrected`, `explanation`, `skill`. Of these, `original`, `explanation`, and `skill` (mapped to `skill_id`/`error_type`) get persisted to `DetectedError`. **`corrected` — the actual fixed phrase — is computed but never persisted anywhere; it exists only in that one HTTP response.** A silent-loss edge case also exists: if the AI's `skill` label doesn't map to a seeded `Skill` row, the whole correction (including the `DetectedError` row and the learning event) is dropped with no error surfaced.

---

## 4.2 Data Availability Matrix

| Required Data | Current Source | Quality | Reusable? | Action |
|---|---|---|---|---|
| Weak skill detection | `SkillMastery.mastery` (per skill, live query) | Real, current snapshot | Yes | REUSE EXISTING |
| Improving skill detection | *(none directly)* — `SkillMastery` has no history to diff against | Not available as a snapshot; a *proxy* is derivable from `LearningEvent`'s weekly accuracy trend (already computed per-skill-less; per-skill would need a new grouped query) | Partial | SMALL ADDITIVE CHANGE (new grouped query, no schema change) |
| Recent mistakes (with detail: what was typed, what was correct, when) | `ExerciseAttempt` + `PracticeQuestion` (`submitted_answer`, `correct_answer`, `is_correct`, timestamp), joined via `LessonAttempt`/`PracticeSession` for `user_id` | Real, complete for lesson/practice exercises | Yes | SMALL ADDITIVE CHANGE (new repository query function; no new column) |
| Repeated mistakes | No existing grouping query; `get_missed_exercise_ids` gives an unbounded, timestamp-less set of exercise IDs ever missed per skill | Partial — can group by `skill_id` or `exercise_id` reliably; cannot group by finer-grained "concept" without new classification work | Partially | SMALL ADDITIVE CHANGE (group existing rows by skill_id/exercise_id; do not claim finer grouping than the data supports) |
| Accuracy trend | `analytics_repository.get_weekly_correctness_trend_for_user` (already built, per-user, 8-week) | Real | Yes | REUSE EXISTING |
| Daily activity | `LearningEvent.created_at` per day (derivable); `analytics_repository`'s per-user completion stats | Real | Yes | REUSE EXISTING |
| Review-due content | `learner_model_repository.list_due_for_review` (already used by `/me/review`) | Real | Yes | REUSE EXISTING |
| Lesson progress | `LessonAttempt`/per-lesson `completed` flag (added earlier this session on `GET /courses/{id}`) | Real | Yes | REUSE EXISTING |
| Listening errors (word-level detail) | `ExerciseAttempt.correct_answer` JSONB, for LISTENING exercises, already contains the full `category`/`words_correct`/`words_missing`/`words_incorrect`/`explanation` payload from `listening_evaluation.py` | Real, rich, already persisted (not just returned-and-discarded) | Yes | REUSE EXISTING (needs a query, not a schema change) |
| Tutor corrections — the mistake itself | `DetectedError` (`submitted_text`, `description`, `skill_id`, `error_type`, `severity`, `created_at`) for `conversation_message_id`-sourced rows | Real | Yes | REUSE EXISTING |
| Tutor corrections — the "correct" text | **Not stored anywhere** — computed by the AI, returned in one HTTP response, then discarded | Not available | No | SCHEMA CHANGE REQUIRED if this is wanted (new nullable column) — see §4.5 and §4.6 |
| Recommendation reasons (structured) | `practice_service._reason_for_exercise` / `PracticeReasonOut` | Real | Yes | REUSE EXISTING |
| AI cost/rate-limit infrastructure | `app/api/deps.py::get_metered_ai_provider`, `app/core/rate_limit.py`, `app/ai/metering.py` | Real, working, tested | Yes | REUSE EXISTING |
| A generic "cache a computed value with an expiry" utility | Does not exist. Only precedent is `speech_service._speech_cache`, an unbounded in-memory per-process dict with no TTL concept, and Redis is used exclusively for rate-limit counters | N/A | No | Needs a new, small pattern — see §4.6 and §6 (Coach refresh strategy) |

---

## 4.3 V3.1 Audit — AI Learning Coach

| Insight | Classification | Basis |
|---|---|---|
| Weak skill insight | **SUPPORTED NOW** | `SkillMastery` sorted ascending, already exposed via `/me/mastery` |
| Recent performance insight | **SUPPORTED NOW** | `get_learner_activity`'s weekly accuracy trend |
| Repeated mistake insight (by skill) | **SUPPORTED NOW** | `count_recent_incorrect` (windowed count) + a new query grouping `ExerciseAttempt`/`PracticeQuestion` wrong answers by `skill_id` |
| Recent mistake insight (specific examples, "you wrote X") | **SUPPORTED WITH SMALL BACKEND ADDITION** | Data exists in `ExerciseAttempt`/`PracticeQuestion`; needs a new query function to surface it, no schema change |
| Improving skill insight (genuinely "improving," not just "currently high") | **SUPPORTED WITH SMALL BACKEND ADDITION** | Requires comparing accuracy in a recent window vs. an earlier window per skill — derivable from `LearningEvent` (has `skill_id` + `created_at` + `is_correct`) via a new grouped query; `SkillMastery`'s single current value cannot show a trend by itself |
| Activity insight ("you've studied N days this week") | **SUPPORTED NOW** | `LearningEvent`/`LessonAttempt`/`PracticeSession` timestamps, already partially surfaced via `get_learner_activity` |
| Review recommendations | **SUPPORTED NOW** | `list_due_for_review`, already exposed via `/me/review` |
| Tutor-conversation-specific weaknesses | **SUPPORTED NOW** (the mistake itself) / **NOT YET POSSIBLE** (showing the correction text, since it isn't persisted) | See §4.1/§4.2 |

**Overall**: the Coach's grounding context can be built entirely from data that is either already exposed via existing endpoints/services or reachable with small, additive query functions — no schema change is required for a genuinely-grounded V3.1, provided the Coach does not attempt to narrate AI-tutor correction *text* (only that a mistake occurred, on which skill, and roughly why).

## 4.4 V3.2 Audit — Personalized Daily Plan

| Task type | Classification | Basis |
|---|---|---|
| Review tasks | **SUPPORTED NOW** | `list_due_for_review` |
| Continue-learning tasks | **SUPPORTED NOW** | Existing `/courses/{id}` per-lesson completion + the dashboard's existing "next lesson" logic |
| Practice tasks (weak-skill-targeted) | **SUPPORTED NOW** | `recommendation.rank_skills` + `practice_service._select_exercise_for_skill` — this is exactly what `POST /practice/start` already does; a Daily Plan "practice" task can literally be a link into the existing practice flow, not a new selection engine |
| Listening tasks | **SUPPORTED WITH SMALL BACKEND ADDITION** | No existing signal specifically flags "learner needs more listening practice" — would need a small addition (e.g., comparing accuracy on LISTENING-type exercises specifically) or could be reasonably omitted from v1 rather than fabricated |
| Weak-skill tasks | **SUPPORTED NOW** | Same as practice tasks |
| Estimated durations | **NOT YET POSSIBLE** | No duration data is captured anywhere (`response_time_ms` on `LearningEvent` exists as a column but is never populated by any current frontend code) — per the spec's own instruction, this must be omitted rather than invented |
| Task prioritization | **SUPPORTED NOW** | `recommendation.compute_skill_priority` already encodes a real, tested priority order (weakness + review-due + recent mistakes); a Daily Plan should reuse this ordering rather than invent a separate one |

**New/edge-case user states** — all answerable from existing data, none require fabrication:
- **Brand new user**: no `SkillMastery` rows exist yet → no review, no weak-skill practice possible → plan should show only "start your first lesson" (derivable from `CourseDetailOut`, already real).
- **No weak skills yet**: `SkillMastery` rows exist but nothing scores as meaningfully weak → plan naturally deprioritizes practice, favors continue-learning.
- **No review due**: `list_due_for_review` returns empty → omit that task type, don't fabricate one.
- **Hasn't studied recently**: derivable from `last_practiced_at`/`LearningEvent.created_at` — could inform tone/messaging but isn't a blocker to generating a plan.
- **All available content completed**: `CourseDetailOut`'s per-lesson `completed` flags all true → continue-learning task should be omitted, not shown as broken.
- **Insufficient data generally**: every task type above degrades to "omit that section" rather than needing a special-cased "not enough data" state at the data layer — the *UI* needs to handle an empty/near-empty plan gracefully (per §8.5 of the original spec), but the *backend* doesn't need new data to know when to omit.

## 4.5 V3.3 Audit — Mistake Notebook

**Can real historical mistakes be retrieved? Yes, for lesson and practice exercises — confirmed via direct model inspection, not assumed:**

- `ExerciseAttempt` (`app/models/progress.py`): `submitted_answer` (JSONB, NOT NULL), `correct_answer` (JSONB, NOT NULL), `is_correct` (bool, NOT NULL), `explanation` (nullable text), `created_at`. Reachable per-user via `lesson_attempt_id → LessonAttempt.user_id` (no direct `user_id` column).
- `PracticeQuestion` (`app/models/practice.py`): identical shape, nullable until answered, reachable via `practice_session_id → PracticeSession.user_id`.
- For LISTENING exercises specifically, `correct_answer` already contains the full deterministic word-level diff (`category`, `words_correct`, `words_missing`, `words_incorrect`, `explanation`) computed by `listening_evaluation.py` — genuinely rich data, already in the database, not just in a past HTTP response.
- **Neither table has an existing query function filtering by `is_correct = false`**, and neither has an index supporting that filter efficiently at scale — a new repository function (and, if this table grows large in practice, a new index) is needed, but **no new column or table**.

**AI Tutor conversations — partial, with an explicit, real gap:**
- The mistake itself (what the learner wrote) IS retrievable and safely attributable: `DetectedError.submitted_text` + `description` + `skill_id` + `error_type` + `created_at`, already scoped per-user via `evaluation_repository.list_recent_errors`.
- **The corrected version is NOT retrievable** — confirmed by reading `conversation_service.py::_record_correction` in full: only `original`, `explanation`, and `skill` get written to `DetectedError`; the AI's `corrected` field is used only to build that turn's HTTP response and is discarded afterward. **Per the explicit instruction not to add AI Tutor mistakes without a reliable structured correction record: a Mistake Notebook must either (a) show tutor mistakes without a "corrected" side (original + explanation + skill only, which IS honest and real), or (b) require the small schema change described in §4.6 to persist `corrected_text` going forward.** Showing a fabricated or re-generated-on-the-fly "corrected" answer as if it were the historical record would violate the explicit "original answer data remains the source of truth" instruction.
- A related, real edge case: `_record_correction` silently drops a correction entirely (no `DetectedError` row, no learning event) if the AI's `skill` label doesn't match a seeded `Skill.code`. This means the Mistake Notebook's tutor-mistake count could under-represent what the learner actually saw in a conversation. Not a blocker, but worth surfacing as a known limitation rather than silently accepting an undercount as complete.

**Repeated mistakes**: can be grouped reliably by `skill_id` (real FK on every source) or by `exercise_id` (exact same exercise missed more than once — real and precise). Cannot be grouped by a finer "grammar concept"/"vocabulary item" level without new classification logic that doesn't exist today (`DetectedError.description` is free text, not a controlled vocabulary) — per the explicit instruction, mistakes should be shown individually rather than pretending a shared-concept grouping exists when it doesn't.

**"Practice Again"**: `practice_service`'s existing exercise-selection machinery already supports skill-targeted selection (`_select_exercise_for_skill(db, user_id, skill_id, target_difficulty)`), and `_select_exercise_for_skill` already **prioritizes previously-missed exercises for that skill** (`get_missed_exercise_ids`) before falling back to difficulty-matching. This means "Practice Again" for a specific mistake can very plausibly be implemented as: start (or add to) a practice session targeted at that mistake's `skill_id`, reusing the exact existing engine — no second practice engine needed. Confirming this integrates cleanly (rather than needing a new exercise-selection code path) is implementation-detail work reserved for the approved-plan phase, not asserted as done here.

## 4.6 Required Backend Changes

| Change | Classification | Notes |
|---|---|---|
| Query: recent wrong `ExerciseAttempt`/`PracticeQuestion` rows per user, paginated | **SMALL ADDITIVE CHANGE** | New repository function(s), reusing existing tables/columns |
| Query: per-skill accuracy in a recent window vs. an earlier window (for "improving skills") | **SMALL ADDITIVE CHANGE** | New grouped query over `LearningEvent`, same UTC-safe bucketing pattern already used throughout `analytics_repository.py` |
| Query: group wrong attempts by `skill_id`/`exercise_id` (repeated mistakes) | **SMALL ADDITIVE CHANGE** | New repository function; no schema change |
| Endpoint(s): AI Coach insight, Daily Plan, Mistake Notebook | **SMALL ADDITIVE CHANGE** | New routers/endpoints following the existing `deps.py`/auth/rate-limit/schema conventions — no architectural change |
| `DetectedError.corrected_text` (nullable) so future AI-tutor corrections can show a real "should have been" | **SCHEMA CHANGE REQUIRED, IF WANTED** | Only needed if the Mistake Notebook must show corrected text for tutor mistakes. **Alternative that requires no schema change**: show tutor mistakes without a corrected-text field (original + explanation + skill only) — genuinely honest, just less complete. This is a decision for the approval step, not decided unilaterally here. |
| Any form of "second learner model," parallel mastery calculation, or parallel recommendation engine | **NOT JUSTIFIED** | Everything V3 needs is either already computed (`SkillCandidate`/`compute_skill_priority`/`SkillMastery`) or a thin additive query on top of existing tables — rules.md and the task's own instructions explicitly forbid duplicating this |
| A generic Redis/DB value-cache utility with TTL, for the Coach's "regenerate at most once a day" behavior | **SMALL ADDITIVE CHANGE (new, but small)** | No existing generic cache-with-expiry utility exists anywhere in the codebase to reuse (confirmed by direct grep) — the simplest fit consistent with this codebase's Postgres-first bias is a small table or column storing `generated_at`/the insight payload, checked against a UTC day boundary the same way `analytics_repository._utc_day_bounds` already does elsewhere, rather than introducing Redis value-caching as a new pattern for one feature |
| Daily Plan persistence (if chosen over dynamic generation) | **Undetermined pending approval** — plausibly **NOT JUSTIFIED** | The plan's inputs (`SkillCandidate` ranking, review-due, lesson completion) are all fast, already-indexed queries; dynamic generation on each `GET` is likely sufficient without a new table. A completion-tracking mechanism (marking a plan item "done" when the underlying real activity happens) does **not** need its own table either — completion can be derived by re-checking the same real data (e.g., "is this skill still the top-ranked recommendation," "is this lesson now completed") rather than storing separate plan-state. This will be confirmed, not assumed, during implementation planning. |

## 4.7 Risks

- **Data quality**: `LearningEvent.response_time_ms` is a real column that is never populated — any V3 feature must not silently assume it has data (confirmed empty in every current write path).
- **AI hallucination**: the AI Coach must be grounded in a structured context object built entirely from the real queries above; the existing precedent (`evaluation_service.py`'s strict Pydantic Raw/normalized schema validation, raising `AIResponseValidationError` on malformed output rather than retrying with a guess) is the pattern to follow, not a new, looser one.
- **Privacy**: `DetectedError.submitted_text` and `ExerciseAttempt.submitted_answer` contain real learner-authored text; an AI Coach prompt must send only aggregated/structured signals (skill names, mastery numbers, counts) to the LLM, not raw submitted text, unless a specific feature genuinely requires it and that's called out explicitly during planning.
- **Cost**: `AI_RATE_LIMIT_PER_HOUR = 30` (per user, shared across ALL AI-touching endpoints via `get_metered_ai_provider`) already applies to any new Coach endpoint automatically — but a Coach that regenerates on every page view would burn through a user's shared AI budget fast and starve their AI Tutor usage; a real refresh policy (not "call on every render") is required, per the task's own explicit instruction.
- **Query scalability**: neither `ExerciseAttempt` nor `PracticeQuestion` currently has an index supporting `WHERE is_correct = false` efficiently — fine at this project's current data volume, worth flagging for the planning step rather than ignoring.
- **Duplicate logic**: the single biggest architectural risk this audit was specifically asked to check for. Finding: it's avoidable — `SkillCandidate`/`rank_skills`/`compute_skill_priority` (recommendation.py) and `PracticeReasonOut`-style structured reasoning (practice_service.py) already exist and are directly reusable by both the Coach and the Daily Plan; a shared "learner insight" aggregation layer (per the task's own §6) should be built once and consumed by all three V3 features, not reimplemented per-feature.
- **Incorrect learner insight risk**: the "improving skills" and "repeated mistakes" insights are the two areas where it would be easiest to overclaim precision the data doesn't support (e.g., claiming two mistakes share a "concept" when only `skill_id` is actually known) — §4.5 above documents exactly where the line is.

---

## Summary for the approval decision

- **No database migration is required** for V3.1 (Coach) or V3.2 (Daily Plan) — both are fully supportable by new query functions over existing tables.
- **V3.3 (Mistake Notebook) does not require a migration either**, for lesson- and practice-exercise mistakes (the large majority of mistake data) — the data already exists in `ExerciseAttempt`/`PracticeQuestion`. A migration (one new nullable column, `DetectedError.corrected_text`) is optional and only needed if AI-tutor conversation mistakes must show a real "corrected" answer rather than being shown without one.
- A shared "learner insight aggregator" service, built once on top of `recommendation.py`'s existing `SkillCandidate`, is the correct foundation for all three features, per the task's own architectural principle — this avoids the single biggest risk (duplicated weak-skill/accuracy logic across three endpoints).
- Existing AI cost controls (`get_metered_ai_provider`, 30 calls/hour/user) and the existing structured-AI-output-validation precedent (`evaluation_service.py`) are both directly reusable for the Coach with no new infrastructure.

**This audit does not include a detailed implementation plan** — per the task's explicit instruction to stop after the audit. A concrete plan (exact endpoints, exact shared-service shape, the `DetectedError.corrected_text` decision, and Daily Plan persistence-vs-dynamic decision) is ready to be drafted for approval as the next step, once this audit itself has been reviewed.
