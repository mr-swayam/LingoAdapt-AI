# V3 Adaptive Learning Intelligence — Revised Implementation Plan

**Status: complete, approved design. No implementation has occurred.** This is the full, non-summarized plan persisted from the planning session, incorporating both rounds of external architecture review (12 findings, then 5 more). It is consistent with `V3_ADAPTIVE_INTELLIGENCE_AUDIT.md`, which remains the source of truth for what learner data exists — this document is the "what to build and how" layer on top of that audit's "what's available" findings.

**Foundational decisions confirmed across both review rounds:**
1. Mistake Notebook entries from AI Tutor conversations show only what's genuinely persisted (original mistake, explanation, skill) — no `corrected_text` column, no migration.
2. Daily Plan is generated dynamically on every request from live data — no `daily_plans` table, no stored task-completion checkbox.
3. AI Coach reuses Redis (already running in this stack for rate limiting) as a short-lived cache — not a new database table, not "no caching at all."

**Result: V3 ships with zero database migrations**, while still reusing existing infrastructure (Redis) rather than skipping real requirements to avoid one.

---

## 1. V3.1 — AI Learning Coach

### Exact learner data / context used
Built from a new shared `learner_insight_service.py` (§4), never computed redundantly inside the Coach itself:
- Weak skills (`SkillMastery`, `attempt_count > 0`, ascending mastery).
- Improving skills (new logic — see §4's exact thresholds).
- Review priorities (`list_due_for_review`, reused as-is).
- Recent activity summary (`analytics_service.get_learner_activity`, reused as-is).
- Repeated mistakes (Type A / Type B — see §3, reused via the shared layer).

### Separation of observed facts, deterministic trends, and AI recommendations
`CoachContext` is explicitly split into two named sections before it ever reaches a prompt:
- `observed_facts` — skill name, mastery value, attempt_count, current review status. Direct DB reads, zero computation beyond formatting.
- `calculated_trends` — recent-vs-previous accuracy deltas, repeated-mistake counts. Deterministic computations over the facts above — still zero AI involvement.
- The AI is permitted exactly one synthesized field: `recommended_action`. The system prompt explicitly instructs that `summary`/`strengths`/`focus_areas` must be grounded restatements of the supplied `observed_facts`/`calculated_trends` — never introducing a statistic, event, or claim not present in the supplied context — while `recommended_action` is the only field allowed to go beyond restating supplied data. This is a prompt-and-schema-level mitigation, not a runtime-enforced guarantee (an LLM can still deviate) — documented honestly as such, consistent with this codebase's existing precedent (`evaluation_service.py`'s equally strict system prompt + schema validation) rather than an overclaimed hard guarantee.
- **Only keys with real backing data are included.** An empty `improving_skills` result is omitted from the context entirely — never sent as an empty list for the model to potentially over-interpret or comment on.

### Structured output and validation
New `backend/app/schemas/coach.py`, mirroring `schemas/evaluation.py`'s exact Raw/normalized split:
- `RawCoachInsight` (strict, AI-facing): `summary: str`, `strengths: list[str]`, `focus_areas: list[str]`, `recommended_action: str`, `data_note: str | None`.
- `CoachInsightOut` (normalized, app-facing): same shape.
- Validation: `json.loads(response.content)` then `RawCoachInsight.model_validate(...)`, both in one `try/except (json.JSONDecodeError, ValidationError)` — on failure, log a warning with the raw content (`logger.warning("ai_coach_schema_invalid content=%r error=%s", ...)`) and raise the **existing** `AIResponseValidationError` (from `app/ai/exceptions.py`, reused as-is, no new exception type). Never retried with a guess, never silently replaced with a fabricated fallback insight.

### Insufficient-data behavior
If the learner has no `SkillMastery` rows with `attempt_count > 0` (i.e., essentially no history), the AI call is **skipped entirely** — the endpoint returns the deterministic message from the original spec verbatim: *"Complete a few more learning activities so I can give you a more personalized analysis."* Zero AI cost, zero hallucination risk for a case where there is nothing real to ground a response in. This renders on the frontend as a normal, calm state — not an error card.

### Caching strategy
Redis-backed, short-lived, read-through cache — **not** a new database table, **not** "no caching at all":
- `GET /me/coach` checks the cache first; on a hit, serves the cached insight without touching the AI provider at all.
- On a miss, generates via the AI provider, then writes to the cache before returning.
- TTL on the order of hours (exact value fixed and documented at implementation time as a named constant, not a magic number left implicit).

### Cache key strategy
`coach_insight:{user_id}` — namespaced by the authenticated user's UUID, exactly mirroring the existing rate-limit key convention (`ratelimit:ai:{user_id}`, `ratelimit:auth:{client_ip}`) already established in `app/api/deps.py`. This guarantees per-user isolation at the key level — no cross-user cache collisions are structurally possible, since two different users can never produce the same key.

### Meaningful learner-state cache invalidation
The cache is explicitly invalidated (key deleted) at the two points this app already treats as a real completion milestone — a lesson transitioning to `COMPLETED` (inside `lesson_service.submit_answer`'s existing completion branch) and a practice session transitioning to `COMPLETED` (inside `practice_service.submit_practice_answer`'s existing completion branch). Deliberately **not** invalidated per single exercise answer — that would defeat the purpose of caching during an active session. This reuses exactly the granularity this app already treats as "a real milestone happened" (XP awards and achievement checks already fire at these same two points, not per-answer) rather than inventing a new boundary.

### Redis failure behavior
If Redis is unreachable, the Coach **still works** — it falls open exactly the way `check_rate_limit` already does (catch `redis.RedisError`, log a warning, proceed without the cache: generate fresh every time until Redis recovers). A caching layer must never become a hard failure point for a feature that would otherwise work fine.

### Manual refresh cooldown / protection
The explicit "Refresh" action (frontend button) deletes the cache key before re-requesting, but is itself gated by a **second, tighter, Coach-refresh-specific** rate limit — reusing the exact existing `check_rate_limit(key, limit, window_seconds)` primitive from `app/core/rate_limit.py` with its own key: `ratelimit:coach-refresh:{user_id}`, `limit=1`, `window_seconds=300` (one explicit refresh per 5 minutes). A refresh request inside the cooldown returns 429 with a clear message. This is independent of, and tighter than, the general AI budget below — it exists specifically so rapid button-mashing on one feature can't burn through the budget meant to cover the whole app's AI usage.

### AI rate/cost controls
On top of everything above, every actual AI provider call still goes through the **existing, unmodified** `Depends(get_metered_ai_provider)` — meaning the Coach automatically inherits the shared `AI_RATE_LIMIT_PER_HOUR = 30` per-user budget (shared across every AI-touching endpoint, including the Tutor) and automatic latency/success logging to `ai_call_logs`, with zero new AI infrastructure. The Coach's own cache and refresh-cooldown sit *in front of* this shared gate, reducing how often it's ever actually exercised for this feature specifically.

### Tests and verification requirements
- Insufficient-data short-circuit returns the deterministic message with zero AI provider calls (`FakeAIProvider.chat_calls == 0`).
- `CoachContext` never includes a key with no backing data (e.g., no `improving_skills` key at all when none qualify).
- Malformed/invalid AI JSON raises `AIResponseValidationError`, is logged, and never silently returns a fabricated insight.
- Cache hit: a second `GET /me/coach` within the TTL does not call the AI provider again.
- Cache miss / expiry: after TTL, a call regenerates.
- Redis unavailable: Coach still returns a real (freshly-generated) result; the fail-open path is exercised, not a hard error.
- Activity-triggered invalidation: completing a lesson or practice session between two `GET /me/coach` calls causes the second call to regenerate rather than serve the stale cached value.
- Refresh cooldown: two refresh requests inside 5 minutes yield one success and one 429, using the same fake-Redis-client test pattern already established in `tests/test_rate_limiting.py`.
- Shared AI rate limit still applies: a Coach call counts against the same `ratelimit:ai:{user_id}` budget the Tutor uses (no accidental separate/unlimited budget).
- User isolation: user A's cached insight is never served to user B (verified via distinct cache keys and a real two-user test).

---

## 2. V3.2 — Personalized Daily Plan

### Deterministic generation
`GET /me/daily-plan` is generated fresh on **every** request from live data — no persisted plan, no stored task list, no AI call anywhere in task selection. The same inputs always produce the same output (no randomness anywhere in the ordering or selection logic).

### Exact priority order
Fixed, in this order: **(1) review-due skills → REVIEW tasks, (2) weak skills (via the existing `recommendation.rank_skills` engine, not a reimplementation) → PRACTICE tasks, skipping any skill already covered by a review task above so no skill gets two tasks, (3) the next incomplete lesson (from the already-existing per-lesson `completed` flag on `CourseDetailOut`) → one LESSON task.** Ties within a category are broken by a stable secondary key (priority score, then skill/lesson id) — never random, satisfying the explicit determinism requirement.

### Supported task types only
`TaskType(enum.StrEnum)` with exactly `REVIEW`, `PRACTICE`, `LESSON` — the only three backed by a real, existing recommendation signal today. No `LISTENING`, `SPEAKING`, `CONVERSATION`, or `WRITING` task is ever emitted, because no genuine per-type signal exists yet to justify one (confirmed in the original audit's §4.4 — e.g., there is no existing "this learner specifically needs more listening practice" signal). This is a Python-level enum only — the plan itself is never persisted, so there is no corresponding database enum/migration.

### Extensible task model for future activity types
The plan generator is structured as "evaluate each supported task type in priority order, emit a task only if its real condition is met" — a closed loop over a small, explicit list of type-handlers, not a single monolithic function. Adding a 4th type later (e.g. `LISTENING`, once a real per-type weak-area signal exists) means adding one more handler to that loop and one more enum member — a small additive change, not a redesign. This is the concrete mechanism that keeps V3.2 compatible with a future Next Best Action Engine (§6) without building one now.

### Stable completion semantics
Completion is checked against a **stable, live condition** for every task type, never a per-request timestamp (see §10, item 1 for why the original design was wrong):
- `REVIEW` task: done once its skill no longer appears in `list_due_for_review` — inherently live/stable, unchanged from the original design (this one was never buggy).
- `LESSON` task: done once that lesson's `completed` flag is true — inherently live/stable, unchanged.
- `PRACTICE` task: done once `SkillMastery.last_practiced_at` falls on-or-after the start of **"today"** — where "today" is defined per the explicit local-day strategy immediately below. This is the one that needed fixing, and is now stable under any number of plan regenerations within the same day.

### Explicit learner-local-day / timezone strategy
This application stores **no per-user timezone anywhere** (confirmed by direct grep across `backend/app/models` during the audit) — so "today" cannot silently mean "the learner's actual calendar day" without either storing a timezone (a schema change explicitly not justified for this feature alone) or accepting a client-supplied hint. The chosen strategy: `GET /me/daily-plan` accepts an **optional** `local_date` query parameter (`YYYY-MM-DD`), computed client-side from the browser's actual local date — not a full timestamp, just the calendar date the learner is currently in. When supplied, the backend uses it (bounded into a UTC datetime range using the same `_utc_day_bounds`-shaped helper already used throughout `analytics_repository.py`/`gamification_repository.py`) as the "today" boundary for the `PRACTICE` completion check. When absent (a script, a test, or a client that hasn't been updated), it falls back to server UTC-today, so the endpoint is never broken by a missing parameter — it just falls back to a documented, honest default rather than pretending to know the learner's day. **This is explicitly not silent UTC presented as if it were the learner's calendar day** — the UTC fallback is a stated, secondary behavior, not the primary, hidden one.

### Behavior when the plan is regenerated multiple times
Because every completion check (§ above) re-evaluates a live condition rather than comparing against "when was this specific plan generated," the plan is stable under arbitrary regeneration: fetching it 50 times in one day produces the same task list and the same completion states each time (modulo real activity happening in between, which correctly flips a task to done). No task ever flickers between done/not-done from regeneration alone.

### New-user and insufficient-data states
All handled by **omission**, never fabrication:
- Brand-new user (no `SkillMastery` rows at all): no review tasks, no practice tasks — the plan shows only a "start your first lesson" task (or, if literally no course exists, a genuine empty state, not an error).
- No weak skills yet: the practice-task category is simply absent.
- No review due: the review-task category is simply absent.
- All currently-available content completed: the lesson-task category is simply absent.
- Every category empty simultaneously: the plan shows a genuine "you're all caught up / nothing due right now" state — never a fabricated placeholder task to avoid an empty list.

### All edge cases
Covered above: new user, no weak skills, no review due, no course progress at all, all content completed, partial completion mid-day, multiple regenerations in one day, missing `local_date` parameter, a skill covered by both a review-due condition and a weak-skill condition (deduplicated to one task, not two).

### Tests and verification requirements
- Task selection matches the documented priority order exactly, including the review/practice deduplication-by-skill rule.
- `TaskType` never contains a value outside `REVIEW`/`PRACTICE`/`LESSON`.
- Multi-request completion stability: `GET /me/daily-plan` called twice with a real practice event in between shows the task done on both the immediate post-practice call and a later same-day call.
- Completion resets correctly once the (mocked) day rolls over.
- `local_date` cross-timezone case: a practice event logged at a UTC timestamp that is "yesterday" in one timezone but "today" in another produces the correct completion state for each `local_date` value supplied, and omitting `local_date` entirely still works (UTC fallback), never errors.
- Every edge case in the list above has a dedicated test, not just the happy path.
- User isolation: two users' plans never leak into each other.

---

## 3. V3.3 — Mistake Notebook

### Exact data sources
Three, and only three, all confirmed to hold real, structured, per-user data by direct model inspection during the audit:
1. `ExerciseAttempt` (lesson exercises) — `submitted_answer`/`correct_answer`/`is_correct`/`created_at`, reachable per-user via `lesson_attempt_id → LessonAttempt.user_id`.
2. `PracticeQuestion` (practice exercises) — identical shape, reachable via `practice_session_id → PracticeSession.user_id`.
3. `DetectedError` (SHORT_ANSWER AI-graded errors and AI-tutor conversation corrections) — `submitted_text`/`description`/`skill_id`/`error_type`/`severity`/`created_at`, already per-user (`evaluation_repository.list_recent_errors`).

### Unified mistake representation
New `MistakeRecord` shape spanning all three sources: `id`, `source` (`"LESSON"` | `"PRACTICE"` | `"TUTOR"`), `skill_id`, `skill_name`, `exercise_id` (null for `TUTOR` — needed specifically for the exact-retry ownership check below), `exercise_type` (null for `TUTOR`), `prompt` (null for `TUTOR`), `submitted_text` (rendered from the source JSONB per exercise type, reusing the frontend's existing `FeedbackPanel`/answer-component rendering conventions as the reference rather than inventing new formatting rules), `correct_text` (null for `TUTOR`, see below), `explanation`, `category` (LISTENING mistakes only — the already-persisted word-level diff category from `listening_evaluation.py`, stored in `ExerciseAttempt.correct_answer` JSONB, not recomputed), `created_at`.

### Honest handling of missing historical Tutor corrected text
Confirmed by direct inspection of `conversation_service.py::_record_correction`: of the AI's four correction fields (`original`, `corrected`, `explanation`, `skill`), only `original`, `explanation`, and `skill` (→`skill_id`/`error_type`) are ever persisted to `DetectedError`. **`corrected` is computed by the AI but never saved anywhere** — it exists only in that one turn's HTTP response, then is gone. Per explicit decision confirmed across both review rounds: `TUTOR`-sourced `MistakeRecord`s have `correct_text = None`, always — the Notebook shows the original mistake, the explanation, and the skill, honestly, without a "should have been" side for these specifically. No migration is added to fix this retroactively; a nullable `DetectedError.corrected_text` column is documented as a ready, approved-in-spirit-but-not-built future option (§10, item 7) for *new* corrections going forward, not existing history.

### Filtering and pagination behavior
`GET /me/mistakes` accepts `limit`, `offset`, `skill_id`, `source`, `exercise_type` query parameters. Standard bounded page sizes (a documented default and maximum limit) prevent unbounded responses.

### Pagination correctness boundaries
The three sources are merged in application code, not via a single SQL query (no unified view/table exists). The correct, chosen approach: fetch **`offset + limit` rows from each of the three sources** (not a fixed constant like "100 most recent") before tagging, merge-sorting by `created_at` descending, and slicing to the requested page. This is **always correct for any requested page — no record is ever silently hidden**, at the documented cost of O(offset) re-fetched work per request rather than true cursor-based (keyset) pagination. This tradeoff is explicitly right-sized for a single learner's mistake history (not a platform-wide feed) and has a stated upgrade path — a unified SQL view/materialized projection, or real keyset pagination — if a learner's mistake history ever grows large enough, or deep pagination becomes common enough, for the O(offset) cost to matter. Neither is true at this project's current scale.

### Distinction between repeated skill difficulty and repeated exact exercise mistakes
Two separate, honestly-labeled grouping types, both backed by real foreign-key data, never conflated into one undifferentiated "repeated mistake" concept:
- **Type A — "repeated difficulty"**: ≥2 wrong attempts across *different* `exercise_id`s that share a `skill_id`. UI copy: "Repeated difficulty in {skill_name}."
- **Type B — "repeated exact mistake"**: ≥2 wrong attempts on the *exact same* `exercise_id`. UI copy makes clear this is the same question, not just the same topic.
No attempt is made at any finer semantic/conceptual grouping (e.g. "same grammar concept" beyond what `skill_id` already encodes) — `DetectedError.description` and similar fields are free text, not a controlled vocabulary, so the data genuinely doesn't support finer grouping, and the plan doesn't pretend otherwise.

### Exact exercise retry
"Retry this exercise" — offered on a Type B group or any individual mistake card. Calls `start_targeted_practice_session(db, user_id, *, exercise_ids=[...])`, which uses those exact exercise(s) directly, bypassing the normal exercise-selection step (`_select_exercise_for_skill`) entirely — so the learner genuinely gets the same question back, not a different one from the same skill.

### Skill-level practice
"Practice this skill again" — offered on a Type A group. Calls `start_targeted_practice_session(db, user_id, *, skill_ids=[...])`, which reuses the **existing, unmodified** `_select_exercise_for_skill` logic (already prioritizes previously-missed exercises for that skill before falling back to difficulty-matching) — no second practice engine, no duplicated selection logic. Both entry points share one underlying session-building helper (refactored out of `practice_service.start_practice_session`'s existing loop), so there is exactly one place exercise-selection-into-a-session logic lives.

### User ownership / authorization validation
Because `exercise_id` is **client-supplied input** for the exact-retry entry point (unlike skill-level practice, where the client never picks specific content), every supplied `exercise_id` is verified against that same authenticated user's own wrong-attempt history (via the new mistake-query functions) *before* being used to build a session. Any `exercise_id` that isn't genuinely one of this user's own past mistakes is rejected with a 400 — never silently honored. This prevents a client from using "Retry this exercise" as a way to hand-pick arbitrary content into what's supposed to be a personalized, history-grounded action.

### Tests and verification requirements
- Correct historical retrieval across all three sources, each independently and merged.
- User isolation on every query (a user never sees another user's mistakes).
- Filtering by `skill_id`, `source`, `exercise_type`, individually and combined.
- Pagination correctness at a page depth beyond what a naive fixed-window merge would have covered.
- Empty notebook (new user) renders a genuine empty state, not an error.
- LISTENING mistakes show the real, persisted word-level category/diff data, not recomputed or fabricated.
- Type A vs. Type B grouping: a fixture with 2 wrong attempts on the same exercise plus 1 wrong attempt on a different exercise in the same skill produces both an exercise-level group (count 2) and a skill-level group (count 3), reported distinctly with distinct labels.
- Exact-retry serves precisely the requested exercise(s), never a substitute.
- Skill-level "Practice Again" reuses the existing missed-exercise-prioritizing selection, verified against a fixture with multiple missed exercises in one skill.
- Ownership validation: a second user cannot trigger a retry using an `exercise_id` drawn from the first user's mistake history (403/400, not silently allowed).
- Long submitted/correct answer text renders without layout breakage (frontend).
- Missing `correct_text` for `TUTOR` mistakes renders gracefully and clearly, never as if the record were broken or incomplete.

---

## 4. Shared learner-insight layer

### Exact responsibilities
One new module, `backend/app/services/learner_insight_service.py`, is the **single place** weak-skill, improving-skill, accuracy, and repeated-mistake logic lives — consumed by all three V3 features (Coach, Daily Plan, Mistake Notebook), never recomputed independently inside any of them.

### Existing services/data reused
- `learner_model_repository.list_skill_mastery_for_user` — weak-skill detection (pure reuse, no new query).
- `learner_model_repository.list_due_for_review` — review priorities (pure reuse).
- `analytics_service.get_learner_activity` — recent activity summary (pure reuse).
- `recommendation.rank_skills` / `compute_skill_priority` — the exact existing prioritization engine, reused as-is by the Daily Plan (§2) rather than reimplemented.
- New mistake-query functions (`backend/app/repositories/mistake_repository.py`) feed both the Mistake Notebook (§3) and this layer's `get_repeated_mistakes`.

### No duplicate learner model
Explicitly and structurally avoided: no new mastery formula, no new priority-scoring formula, no parallel "insight" computation that could drift from `SkillMastery`/`recommendation.py`'s existing, tested numbers. Every "how good is this learner at this skill" or "what should they do next" question V3 asks is answered by calling into the same existing functions every other part of this app already relies on.

### Improving-skill calculation
**New logic** (nothing existing computes this today) — per skill, compares accuracy in a recent 7-day window against the 7 days immediately before that, computed from `LearningEvent` (which has `skill_id` + `created_at` + `is_correct` on every row). Implemented as one new repository query following the exact UTC-bounds pattern already established throughout `analytics_repository.py`.

### Explicit sample-size / window / threshold definitions
Fixed now, not deferred to implementation time:
- `IMPROVING_SKILL_RECENT_WINDOW_DAYS = 7`
- `IMPROVING_SKILL_MIN_ATTEMPTS_PER_WINDOW = 3` — a skill is only evaluated for "improving" if **both** the recent and previous windows have at least this many attempts; below that, a swing is noise, not a trend.
- `IMPROVING_SKILL_MIN_ACCURACY_DELTA = 15` (percentage points) — recent accuracy must exceed previous accuracy by at least this much to count as genuinely improving.
These are named constants in `learner_insight_service.py`, matching this codebase's existing convention of tunable-but-explicit thresholds (`pronunciation.CORRECT_THRESHOLD`, `listening_evaluation.MINOR_ERROR_THRESHOLD`) rather than inline magic numbers or numbers left to be decided ad hoc during coding.

### What is not supported by current data
- A true mastery-*over-time* trend (as opposed to accuracy-over-time): `SkillMastery` is a snapshot row updated in place, with no history table — confirmed directly in the audit. "Improving skills" is therefore computed from the raw `LearningEvent` log's accuracy, not from a mastery-value time series that doesn't exist.
- Fine-grained repeated-mistake grouping beyond `skill_id`/`exercise_id` (see §3) — no controlled vocabulary exists to group by "concept" more precisely.
- Response-time-based or other fine-grained confidence signals (see §5).

---

## 5. Goals and confidence

### Current data availability
Checked directly against the schema, not assumed:
- **Learner goals**: `backend/app/models/user.py`'s `UserPreferences` has exactly one goal-adjacent field, `daily_goal_xp: int` — a gamification pacing target (how much XP per day), not a learning objective (e.g. "conversational fluency," "travel Spanish"). `memory.md` §2.A lists `learning_goal`/`preferred_topics`/`preferred_difficulty` as intended profile-memory fields, but **none exist as real columns anywhere** in the current schema (confirmed by direct grep across `backend/app/models`).
- **Fine-grained confidence signals**: response time (`LearningEvent.response_time_ms` — the column exists but is never populated by any current frontend code, confirmed empty in every write path), retries, answer changes, hint usage, audio-replay count, explicit uncertainty — **none of these are tracked anywhere** in the current schema or frontend event flow.

### What is genuinely supported
- `SkillMastery.confidence` (from the existing `mastery.compute_confidence(attempt_count)` — "how much evidence backs this mastery estimate") **is** real, already computed, already stored, and already reused as part of `get_weak_skills`'s output. This answers a coarser question ("how sure are we about this mastery number") than fine-grained per-answer confidence, but it's genuinely real and used honestly where relevant (e.g., the Coach can note low confidence due to few attempts).

### What is future scope
- Learner goals as an input to Coach context, Daily Plan prioritization, or recommendation reasoning — not built, since no usable goal data exists.
- Fine-grained per-answer confidence scoring — not built, since none of its inputs are tracked anywhere today. Would require new frontend instrumentation (not just a backend change) before it could be built honestly.

### No fabricated learner signals
V3 does not invent a goal, does not invent a per-answer confidence score, and does not present the coarser attempt-count-based confidence as if it were the finer signal the architecture review asked about.

---

## 6. Future Next Best Action compatibility

V3 does **not** build a V3.4 Next Best Action Engine now. It prepares for one structurally, via exactly two seams:

1. **`TaskType`, designed for additive growth** (§2): today exactly `REVIEW`, `PRACTICE`, `LESSON` — the only three types with a real, current recommendation signal. `LISTENING`, `SPEAKING`, `CONVERSATION`, `WRITING` are named here as the future set a Next Best Action Engine would eventually choose among, but **none are implemented now** — no fake routes, no placeholder task type, no speculative UI for an activity type the backend can't yet justify recommending. Adding one later is a small, additive change to the plan generator's evaluate-each-type loop, not a redesign.
2. **`learner_insight_service`** (§4) as the single aggregation point: a future engine would consume this same service (plus an expanded `TaskType` set) rather than three independently-duplicated per-feature calculations, which is exactly the "don't calculate weak skills three times" risk the original audit flagged and this plan avoids throughout.

Nothing under this heading is implemented in V3 — it is scope-boundary documentation only, so the choices made in §1–§5 don't have to be revisited when a real Next Best Action Engine is eventually scoped and approved.

---

## 7. Database and infrastructure decisions

| Decision | Required? | Reason |
|---|---|---|
| New database tables | **No** | Every V3 feature is either dynamically generated (Daily Plan) or reads existing tables (`ExerciseAttempt`, `PracticeQuestion`, `DetectedError`, `SkillMastery`, `LearningEvent`) via new query functions, not new storage. |
| New database columns | **No** | Confirmed nothing V3 needs is missing from the existing schema, except the *optional, not-built* `DetectedError.corrected_text` documented in §3/§10 as a future option, explicitly not added now. |
| Migrations | **No** | Direct consequence of the two rows above. |
| Redis usage | **Yes, reusing the existing dependency** | Redis already runs in this stack for rate limiting (`app/core/rate_limit.py`). V3 adds its second real use case: a short-lived value cache for the Coach's generated insight, keyed `coach_insight:{user_id}`, plus a second rate-limit key (`ratelimit:coach-refresh:{user_id}`) using the **existing** `check_rate_limit` function unmodified. This is a new *use* of existing infrastructure, not a new infrastructure dependency. `app/core/rate_limit.py`'s private `_get_redis_client()` is promoted to a public `get_redis_client()` so `coach_service.py` can reuse the exact same client/connection handling rather than duplicating it — the same "promote a private helper once it has a second real caller" pattern already used earlier in this project for `pronunciation.normalize_words`. |
| New indexes | **Possibly, deferred** | Neither `ExerciseAttempt` nor `PracticeQuestion` currently has an index supporting `WHERE is_correct = false` efficiently. Acceptable at this project's current data volume (flagged as a risk in the original audit); not added speculatively — would only be added if real query performance during implementation/testing demonstrates a genuine need, not because it sounds prudent in the abstract. |
| No unnecessary persistence | **Enforced throughout** | Task completion (Daily Plan), coaching insights beyond the Redis cache TTL, and mistake groupings are all computed live from existing tables on every request — nothing is persisted "for convenience" anywhere in this plan. |

---

## 8. Security and data integrity

- **Authenticated-user scoping**: every new endpoint (`GET /me/coach`, `GET /me/daily-plan`, `GET /me/mistakes`, `POST /practice/practice-again`) requires `Depends(get_current_user)`, following the exact existing convention used by every other `/me/*` endpoint in this codebase — no new auth pattern introduced.
- **Exercise ownership checks**: the exact-retry entry point (§3) validates that every client-supplied `exercise_id` belongs to the authenticated user's own wrong-attempt history before use — the one place in V3 where a client supplies an identifier that could otherwise reach across users' data if unchecked.
- **Cache isolation by user**: the Coach's Redis cache key is namespaced by `user_id` (`coach_insight:{user_id}`), structurally preventing any cross-user cache collision — two different users can never produce or read the same key.
- **AI input/output validation**: inputs to the Coach's prompt are limited to the structured, aggregated `observed_facts`/`calculated_trends` context (skill names, numbers, counts) — never raw learner-submitted text (`ExerciseAttempt.submitted_answer`, `DetectedError.submitted_text`) sent wholesale to the model, consistent with minimizing what personal data reaches a third-party AI provider. Output is schema-validated before use, per §1's structured-output section, with no silent fallback on validation failure.
- **Error handling**: malformed AI output raises the existing `AIResponseValidationError` and surfaces as a clean error state, never a leaked raw provider error or stack trace to the client — consistent with this codebase's existing global exception handling (`app/main.py`'s exception handler, `app/core/middleware.py`'s request logging) which every new endpoint inherits automatically without additional code.

---

## 9. Verification plan

- **Regression baseline first, actually run, not assumed**: `pytest -q` (322 passed at last real run), `vitest run` (70 passed at last real run), `ruff check .`, `mypy app`, `eslint .`, `tsc --noEmit`, `next build` — all must stay green throughout implementation, re-verified at the end, not just at the start.
- **New backend tests** — every test listed under each feature's own "Tests and verification requirements" subsection above (§1, §2, §3), following this codebase's established per-file convention: real signup, real database, `FakeAIProvider` for AI paths, not excessive mocking of this project's own code.
- **New frontend tests** — component-level tests for the three new pages' (`/coach`, `/daily-plan`, `/mistakes`) loading/empty/error states, following the existing `vitest` + `@testing-library` convention already used throughout `frontend/src/**/__tests__/`.
- **Integration tests** — the full request path for each new endpoint (auth → service → repository → response shape), not just isolated unit tests of the service functions.
- **Real browser verification** (Playwright, temporarily installed and fully removed afterward, matching the exact pattern already used in the V2 Premium UI phase of this project): the complete learner journey — sign in, complete a real learning activity, view the Coach and confirm its content is genuinely grounded in what was just done (not generic), view the Daily Plan and confirm task reasons match real data, complete a plan task and confirm the plan reflects it, deliberately make a mistake, find it in the Mistake Notebook, use Practice Again (both the exact-retry and skill-level variants), complete the resulting practice, and confirm the learner's real data updated as a result.
- **Accessibility checks** — a real axe-core scan of all three new pages, at the viewports already established as this project's standard (desktop/tablet/mobile), with any serious/critical finding fixed, not suppressed.
- **Regression checks** — explicit re-verification that nothing existing broke: authentication, lesson completion, XP, mastery updates, personalized practice (the *existing*, non-targeted flow), AI Tutor (text and voice), Listening Practice, and the existing analytics/progress endpoints.
- **Exact conditions required before calling V3 complete**: all of the above green, all new tests passing, real (not simulated) browser verification of the full journey completed and documented with actual results, zero regressions in the existing suite, and a final `V3_ADAPTIVE_INTELLIGENCE_REPORT.md` written honestly against what was actually verified — not claimed without evidence.

---

## 10. External Architecture Review Revisions

Every issue raised across both review rounds, with the format requested: original issue → final decision → reason → implementation consequence → verification requirement.

**1. Daily Plan completion boundary was unstable.**
- *Original issue*: a practice task counted "done" if `SkillMastery.last_practiced_at` was more recent than the timestamp of the *current* `GET` request — but the plan regenerates on every `GET`, so that comparison basis is a different, later value each time, and doesn't behave as a stable "done for today" check across multiple fetches in one day.
- *Final decision*: every task type's completion is checked against a stable, live condition — `REVIEW` via `list_due_for_review` membership, `LESSON` via the `completed` flag, `PRACTICE` via `last_practiced_at` compared against the start of "today" (§2's local-day strategy), never against "when was this specific plan request made."
- *Reason*: only a comparison anchored to something that doesn't itself change on every request (a due-list membership check, a boolean flag, a day boundary) can produce a stable, non-flickering completion state under arbitrary regeneration frequency.
- *Implementation consequence*: `daily_plan_service.py`'s completion logic must never read "now" as its own comparison anchor for `PRACTICE` tasks — it reads the day boundary derived from `local_date`/UTC-fallback instead.
- *Verification requirement*: multi-request stability test (§2) — task shown done on two calls in the same day with real activity in between, and correctly reset the next day.

**2. Daily Plan task model was closed to 3 hardcoded types.**
- *Original issue*: task selection implicitly only ever produced review/practice/continue-lesson items, with no structure for anything else, unable to grow toward a future Next Best Action Engine without a redesign.
- *Final decision*: `TaskType(enum.StrEnum)` with exactly `REVIEW`/`PRACTICE`/`LESSON` now, structured as an evaluate-each-supported-type loop.
- *Reason*: the spec explicitly asks for an extensible model, but also explicitly forbids exposing unsupported activity types — the loop structure satisfies both without fabricating a `LISTENING`/`SPEAKING`/etc. task the backend can't yet honestly justify.
- *Implementation consequence*: adding a future task type is a small addition to the loop and the enum, not a rewrite of `daily_plan_service.py`'s structure.
- *Verification requirement*: a test asserting the plan never contains a `task_type` outside the 3 currently-implemented values.

**3. AI Coach context didn't separate fact from inference.**
- *Original issue*: a single flat context object with no structural distinction between measured data and AI-generated content risked an AI-authored recommendation reading as if it were a historical fact.
- *Final decision*: `CoachContext` explicitly split into `observed_facts` and `calculated_trends` (both zero-AI, deterministic), with the system prompt confining free synthesis to the single `recommended_action` output field.
- *Reason*: a structural, named separation is checkable (a test can assert the shape) in a way a purely verbal prompt instruction alone is not.
- *Implementation consequence*: `coach_service.py`'s context-building step must produce this two-part shape explicitly, and the prompt template must reference the two parts by name.
- *Verification requirement*: a test on the constructed `CoachContext`'s shape, and a documented (not test-enforced, since it's an LLM) instruction in the system prompt.

**4. AI Coach had no cost/refresh control beyond the shared per-user AI budget.**
- *Original issue*: relying solely on the shared 30/hour AI budget doesn't prevent needless regeneration on every page visit.
- *Final decision*: Redis-backed short-lived caching, reusing the existing Redis dependency and rate-limit client pattern (§1, §7).
- *Reason*: the review specifically asked whether existing infrastructure could support this without new persistence — Redis already runs in this stack and already has a working client; reusing it is strictly better than either skipping the requirement or adding a new database table.
- *Implementation consequence*: `_get_redis_client()` in `app/core/rate_limit.py` becomes public (`get_redis_client()`) for `coach_service.py` to import.
- *Verification requirement*: cache-hit/cache-miss/Redis-unavailable tests (§1).

**5. Mistake Notebook's "repeated mistake" grouping conflated two different claims.**
- *Original issue*: any 2+ wrong attempts sharing a `skill_id` were labeled a single "repeated mistake" concept, overclaiming precision the data doesn't distinguish.
- *Final decision*: Type A ("repeated difficulty," different exercises/same skill) vs. Type B ("repeated exact mistake," same exercise) as two separately-labeled categories.
- *Reason*: "you got two different Past Tense questions wrong" and "you got the exact same question wrong twice" are both real but different facts — the FK data supports distinguishing them precisely, so the UI should.
- *Implementation consequence*: `mistake_service.group_repeated_mistakes` returns two typed collections, not one.
- *Verification requirement*: the 3-attempt fixture test (§3).

**6. "Practice Again" would have implied more precision than it delivers.**
- *Original issue*: a single skill-level-only targeting function couldn't honestly back a "retry this exact mistake" claim for a Type B group, since skill-level selection might serve a different missed exercise in the same skill.
- *Final decision*: two entry points (`exercise_ids` for exact retry, `skill_ids` for skill-level practice) sharing one underlying session-building helper.
- *Reason*: the UI copy must always match what actually happens; two distinct, honestly-labeled actions are needed because they do two distinct things.
- *Implementation consequence*: `start_targeted_practice_session` takes either parameter (not both required), and the frontend only ever shows the action its data supports.
- *Verification requirement*: exact-exercise-served test (§3).

**7. Future AI Tutor correction storage needed a documented (not built) design.**
- *Original issue*: no stated path existed for eventually storing tutor-correction "corrected" text, if ever approved.
- *Final decision*: document (not build) a nullable `DetectedError.corrected_text: Text | None`, populated only for new corrections going forward, existing rows staying `NULL` forever (never backfilled/invented).
- *Reason*: keeps the option available and well-specified for a future, separately-approved change, without adding an unjustified migration now.
- *Implementation consequence*: none for V3 — this is documentation only.
- *Verification requirement*: none for V3 — deferred entirely.

**8. Mistake Notebook's merge-then-paginate approach needed its correctness boundary stated.**
- *Original issue*: a fixed fetch window per source (e.g. 100 rows) silently breaks correctness once a requested page's `offset + limit` exceeds it.
- *Final decision*: fetch `offset + limit` rows from each source (not a fixed constant) before merging.
- *Reason*: this is always correct for any requested page at the cost of extra re-fetched work per request — the right tradeoff at this project's current per-learner data volume, with a stated upgrade path (unified view / keyset pagination) if that stops being true.
- *Implementation consequence*: `mistake_service.list_mistakes`'s per-source fetch size is a function of the request's `offset`/`limit`, not a constant.
- *Verification requirement*: deep-page correctness test (§3).

**9. Learner goals — audited, confirmed not available in usable form.**
- *Original issue*: whether real learner-goal data exists and should feed V3's reasoning was an open question.
- *Final decision*: it does not exist in usable form (only `daily_goal_xp`, a pacing number, not an objective) — V3 does not use a goal signal anywhere.
- *Reason*: confirmed by direct grep against the actual schema, not assumed.
- *Implementation consequence*: none — nothing to build; documented as future scope (§5).
- *Verification requirement*: none required for V3 itself (the "don't fabricate" requirement is satisfied by simply not building this).

**10. Confidence modeling — audited, confirmed no fine-grained signals exist.**
- *Original issue*: whether real per-answer confidence signals (response time, retries, hint usage, etc.) exist and should be used was an open question.
- *Final decision*: none of them are tracked anywhere; only the existing, coarser attempt-count-based `SkillMastery.confidence` is real and reused where relevant.
- *Reason*: confirmed by direct inspection of the schema and frontend event flow.
- *Implementation consequence*: none — nothing new to build; documented as future scope (§5), contingent on new frontend instrumentation that doesn't exist today.
- *Verification requirement*: none required for V3 itself.

**11. Next Best Action Engine preparation — addressed structurally, not as a new system.**
- *Original issue*: whether V3 should build toward a larger future engine, and how, without over-building now.
- *Final decision*: only the two extensibility seams (§6) — an additively-designed `TaskType` and a shared `learner_insight_service` — are built; no V3.4 engine, no placeholder routes, no fake activity types.
- *Reason*: prepares for the future without building speculative infrastructure now.
- *Implementation consequence*: none beyond what §2 and §4 already specify.
- *Verification requirement*: covered by §2's and §4's own tests; no separate V3.4 verification exists because no V3.4 code exists.

**12. Documentation completeness itself.**
- *Original issue*: the review required every revision to be documented with its reasoning and verification needs before implementation proceeds.
- *Final decision*: this section, and the equivalent section in the prior plan-mode document, satisfy that requirement.
- *Reason*: traceability — an external reviewer (or a future session) should be able to see exactly what changed and why without re-deriving it.
- *Implementation consequence*: none beyond documentation itself.
- *Verification requirement*: this document existing, in the repository, is the verification for this item.

**13. UTC day vs. learner-local day — resolved.**
- *Original issue*: item 1's fix used a UTC day boundary, but this app stores no per-user timezone anywhere — a learner outside UTC would see "today" reset at the wrong local time.
- *Final decision*: an optional, client-computed `local_date` query parameter on `GET /me/daily-plan`, with a UTC-today fallback when absent.
- *Reason*: resolves the correctness gap without storing new state (no timezone column, no migration) — a stateless per-request hint is sufficient.
- *Implementation consequence*: the Daily Plan endpoint's signature includes this optional parameter; the completion-boundary calculation branches on its presence.
- *Verification requirement*: cross-timezone test plus the omitted-parameter fallback test (§2).

**14. AI Coach cache invalidation was missing.**
- *Original issue*: a pure TTL-based cache ignores "meaningful new learning activity" as a refresh trigger, which the original spec explicitly required.
- *Final decision*: explicit cache-key deletion at the two existing lesson/practice completion checkpoints.
- *Reason*: reuses an existing "this moment matters" boundary (the same one XP/achievement logic already uses) rather than inventing a new one or invalidating too granularly (per-answer, which would defeat the cache).
- *Implementation consequence*: two additional lines at two existing call sites (`lesson_service.submit_answer`, `practice_service.submit_practice_answer`).
- *Verification requirement*: the activity-triggered invalidation test (§1).

**15. AI Coach manual Refresh had no dedicated rate control.**
- *Original issue*: the Refresh button relied solely on the generous, shared 30/hour AI budget, with nothing preventing rapid repeated presses from consuming it disproportionately.
- *Final decision*: a second, tighter `check_rate_limit`-based cooldown specific to Coach refreshes (1 per 5 minutes).
- *Reason*: reuses the exact existing rate-limiting primitive with a new key — zero new rate-limiting code, just an additional, appropriately-scoped call site.
- *Implementation consequence*: the refresh code path checks this second limit before the shared AI budget is ever reached.
- *Verification requirement*: the refresh-cooldown test (§1).

**16. "Improving skill" thresholds were left undefined.**
- *Original issue*: deferring exact numbers to implementation time risks either an arbitrary in-the-moment choice or drift from what's documented.
- *Final decision*: fixed now — 7-day windows, ≥3 attempts per window, ≥15-point accuracy delta (§4).
- *Reason*: matches this codebase's existing convention of named, tested, documented thresholds rather than inline or deferred magic numbers.
- *Implementation consequence*: three named constants in `learner_insight_service.py`.
- *Verification requirement*: exact-boundary tests (2 vs. 3 attempts, 14 vs. 15 points) (§4).

**17. "Retry this exercise" had no ownership check on the supplied `exercise_id`.**
- *Original issue*: the exact-retry entry point would have accepted any client-supplied `exercise_id` with no verification it was genuinely this learner's own mistake.
- *Final decision*: an explicit ownership check against the user's own wrong-attempt history before honoring the request, rejecting anything that doesn't match.
- *Reason*: `exercise_id` is the one place in V3 where the client supplies a specific content identifier — everywhere else, the client only ever supplies a `skill_id` (which never lets it pick specific content), so this is the one entry point that genuinely needs the check.
- *Implementation consequence*: `mistake_service`/`practice_service`'s targeted-session builder performs this check before constructing a session, not after.
- *Verification requirement*: the cross-user ownership test (§3).

---

## Confirmation that the five explicitly-required final decisions are preserved

- **A.** Daily Plan completion does not depend on the current `GET` request's timestamp — see §2 "Stable completion semantics" and §10 item 1.
- **B.** "Today" has an explicit learner-local-day strategy (`local_date` query parameter, UTC fallback stated as a fallback, not presented as the primary/only definition) — see §2 "Explicit learner-local-day / timezone strategy" and §10 item 13.
- **C.** Coach caching supports both meaningful invalidation (lesson/practice completion) and manual-refresh protection (a dedicated cooldown, separate from the general AI budget) — see §1 "Meaningful learner-state cache invalidation" and "Manual refresh cooldown / protection," and §10 items 14–15.
- **D.** Improving-skill thresholds and minimum sample requirements are explicitly defined (7-day windows, ≥3 attempts, ≥15-point delta) before any implementation begins — see §4 "Explicit sample-size / window / threshold definitions" and §10 item 16.
- **E.** Exact exercise retry verifies the requested exercise is associated with the authenticated user's own mistake history — see §3 "User ownership / authorization validation" and §10 item 17.
