# V3 Adaptive Learning Intelligence — Implementation Report

Status: **V3.1 (AI Learning Coach), V3.2 (Personalized Daily Plan), and V3.3 (Mistake Notebook) are implemented, tested, and verified in a real browser against the live dev stack.** Nothing has been committed or pushed (explicit instruction) — everything described below exists only in the working tree. Full `git status --short` is reproduced in §9.

This report follows `V3_REVISED_IMPLEMENTATION_PLAN.md` section-by-section and reports only what was actually built, run, and observed — no claim below is inferred from the plan without independent verification against the real code, real tests, or a real browser.

---

## 1. Planned work (recap)

Per `V3_REVISED_IMPLEMENTATION_PLAN.md`: a shared `learner_insight_service.py` aggregation layer, then three features on top of it — an AI Learning Coach (cached, grounded, cost-controlled), a dynamically-generated Daily Plan (zero persistence, stable completion), and a Mistake Notebook (unifying three pre-existing but never-surfaced data sources, with Type A/B repeated-mistake grouping and a two-entry-point "Practice Again"). Zero database migrations across all three.

## 2. Actual implementation

### 2.1 Shared layer
- **`backend/app/services/learner_insight_service.py`** (new): `get_weak_skills`, `get_improving_skills` (fixed thresholds — `IMPROVING_SKILL_RECENT_WINDOW_DAYS=7`, `IMPROVING_SKILL_MIN_ATTEMPTS_PER_WINDOW=3`, `IMPROVING_SKILL_MIN_ACCURACY_DELTA=15.0`), `get_review_priorities`, `get_recent_activity_summary`, `get_repeated_mistakes_summary`, `has_any_learning_history`.
- **`backend/app/repositories/learner_model_repository.py`** (modified): added `get_skill_accuracy_in_window` (the windowed-accuracy building block for improving-skill detection).
- **`backend/app/repositories/mistake_repository.py`** (new): `list_wrong_exercise_attempts`, `list_wrong_practice_questions`, `exercise_id_is_a_past_mistake`.
- **`backend/app/repositories/evaluation_repository.py`** (modified): added `list_recent_conversation_errors` — see §3.1 for why this is a new function rather than a reuse of `list_recent_errors` as originally planned.
- Added real ORM `relationship()`s (`ExerciseAttempt.exercise`, `PracticeQuestion.exercise`, `DetectedError.skill`) over already-existing FK columns, so mistake queries can eager-load without N+1s. No schema/migration impact — these are ORM metadata only.

### 2.2 V3.3 Mistake Notebook
- **`backend/app/schemas/mistakes.py`** (new): `MistakeSource`, `RepeatedMistakeType`, `MistakeOut`, `MistakeListOut`, `RepeatedMistakeGroupOut`.
- **`backend/app/services/mistake_service.py`** (new): per-exercise-type submitted/correct-text rendering (mirrors `FeedbackPanel.tsx`'s existing per-type switch, extended with an option-id→text lookup for MULTIPLE_CHOICE/WORD_ORDER/MATCHING, which `FeedbackPanel` never needed since it only renders the correct side); `list_mistakes` (merge across 3 sources, `offset+limit+1`-per-source fetch depth — proven correct for any page in the function's own docstring, not just asserted); `group_repeated_mistakes` (Type A/B, using an "occasion key" — `exercise_id` if present else the mistake's own id — so a skill whose every wrong attempt shares one exercise never also gets a redundant Type A group).
- **`backend/app/services/practice_service.py`** (modified): extracted `_create_session_with_exercises` (shared by ranked and targeted selection); added `start_targeted_practice_session(db, user_id, *, skill_ids=None, exercise_ids=None)`; added `_abandon_existing_in_progress_session` (see §3.3); ownership check via `mistake_repository.exercise_id_is_a_past_mistake` before honoring any `exercise_ids` target; coach-cache invalidation call at session completion.
- **`backend/app/services/lesson_service.py`** (modified): coach-cache invalidation call at lesson completion.
- **New endpoints**: `GET /me/mistakes` (paginated, filterable by `skill_id`/`source`/`exercise_type`), `GET /me/mistakes/repeated`, `POST /practice/practice-again`.
- **Frontend**: `frontend/src/app/(app)/mistakes/page.tsx` (new), `frontend/src/lib/mistakes-api.ts` (new), `frontend/src/types/mistakes.ts` (new), `practiceAgain` added to `frontend/src/lib/practice-api.ts`. Dashboard and Progress pages link to it.

### 2.3 V3.2 Personalized Daily Plan
- **`backend/app/schemas/daily_plan.py`** (new): `TaskType` (`REVIEW`/`PRACTICE`/`LESSON`), `DailyPlanTaskOut`, `DailyPlanOut`.
- **`backend/app/services/daily_plan_service.py`** (new): `get_daily_plan(db, user_id, local_date=None)` — REVIEW tasks from `list_due_for_review`, PRACTICE tasks from `practice_service.build_skill_candidates` + `recommendation.rank_skills` (promoted from a `practice_service`-private helper to a shared public one — see §3.2), one LESSON task from the first not-yet-completed lesson in course/unit/lesson position order (via `gamification_repository.get_completed_lesson_ids`, the same completion source `CourseDetailOut` already uses). Skill-level dedup so no skill produces two tasks.
- **New endpoint**: `GET /me/daily-plan?local_date=YYYY-MM-DD` (optional; falls back to server UTC-today).
- **Frontend**: `frontend/src/lib/daily-plan-api.ts` (new, includes `todayLocalDate()` — browser-local calendar date via local `Date` getters, never UTC ones). Dashboard's old "Review due" and "Recommended for you" cards were replaced with one unified "Today's Plan" list (see §3.4 for what was *not* replaced and why).

### 2.4 V3.1 AI Learning Coach
- **`backend/app/schemas/coach.py`** (new): `RawCoachInsight`/`CoachInsightOut` (Raw/normalized split, mirroring `schemas/evaluation.py`), `InsufficientDataCoachInsight`, `CoachResponseOut` (the actual endpoint response — one shape covering both outcomes).
- **`backend/app/services/coach_service.py`** (new): `_build_context` (explicit `observed_facts`/`calculated_trends` split, keys omitted entirely when there's no backing data — verified by inspecting the literal JSON sent to the AI, not just the internal function); insufficient-data short-circuit (zero AI cost); Redis caching (`coach_insight:{user_id}`, 6-hour TTL, fail-open on Redis errors); `invalidate_coach_cache` (called from both completion checkpoints); strict system prompt + `RawCoachInsight` schema validation, raising the existing `AIResponseValidationError` on malformed output (never retried, never faked).
- **`backend/app/core/rate_limit.py`** (modified): `_get_redis_client` promoted to public `get_redis_client` — Redis's second real use case after rate limiting, exactly as planned.
- **`backend/app/api/deps.py`** (modified): `coach_refresh_rate_limit_gate` (`limit=1, window_seconds=300`), applied only to the refresh endpoint, on top of the existing shared `AI_RATE_LIMIT_PER_HOUR`.
- **New endpoints**: `GET /me/coach`, `POST /me/coach/refresh`.
- **Frontend**: `frontend/src/app/(app)/coach/page.tsx` (new), `frontend/src/lib/coach-api.ts` (new), `frontend/src/types/coach.ts` (new). Reachable from a Dashboard card.

### 2.5 Zero migrations, confirmed
No new tables, no new columns, no Alembic revision anywhere in this change set. `git status --short` (§9) shows no `alembic/versions/` entry. The only "new infrastructure" is the second real use of the already-running Redis (matching the plan's explicit item 4).

---

## 3. Deviations from the plan (found and resolved, not silently substituted)

Per instruction #3, each of these was a real constraint discovered against the actual codebase, not a preference — each is documented here with what was found, what was done instead, and why.

**3.1 — `DetectedError` is not exclusively tutor-sourced.** The plan's §1 said Mistake Notebook's TUTOR source could reuse `evaluation_repository.list_recent_errors` directly. While implementing `mistake_repository.py`, I found `ai_grading.grade_short_answer` also writes `DetectedError` rows (with `exercise_id` set) for SHORT_ANSWER lesson/practice mistakes — these are sub-details of a mistake already surfaced via `ExerciseAttempt`/`PracticeQuestion`, not a separate tutor mistake. Reusing `list_recent_errors` as-is would have double-counted and mislabeled these. **Resolution**: added a new, narrowly-scoped `list_recent_conversation_errors` (filtered to `conversation_message_id IS NOT NULL`), leaving `list_recent_errors` completely untouched so `GET /me/errors` (existing, tested, used by the Progress page) keeps its current behavior. Verified with `test_short_answer_exercise_mistake_is_not_double_counted_as_a_tutor_mistake`.

**3.2 — `build_skill_candidates` needed to be shared, not duplicated.** The Daily Plan's PRACTICE tasks need the exact same candidate-building logic `practice_service.py` already had as a private `_build_candidates`. Reusing a private, underscore-prefixed function across modules would have been a real code smell and a duplicate-logic risk if it ever drifted. **Resolution**: renamed it to public `build_skill_candidates` in `practice_service.py` (single call site of truth), imported by `daily_plan_service.py`. `recommendation.py` itself was deliberately left untouched (it's a pure, DB-independent module by design; adding a DB-querying function there would have blurred that boundary).

**3.3 — The in-progress-session interaction the plan flagged as "to be verified, not assumed."** `practice_repository.get_in_progress_session` uses `scalar_one_or_none()`, which raises if two `IN_PROGRESS` sessions ever exist for one user — nothing in the schema enforces "at most one" as a real constraint. A naive `start_targeted_practice_session` would have let a second one exist alongside a general session, crashing the next `/practice/start` call. **Resolution**: `_abandon_existing_in_progress_session` force-completes (not deletes) any existing in-progress session before creating a targeted one — real `correct_count`/`total_count` are left exactly as they are, only `status`/`completed_at` change, reusing the existing `COMPLETED` vocabulary (no new enum member, no migration — `PracticeSessionStatus` is a native Postgres enum). Verified with `test_practice_again_abandons_an_existing_general_in_progress_session`, which asserts a subsequent `/practice/start` call resumes the targeted session rather than crashing.

**3.4 — `TaskType`'s folder placement.** The plan's exact words placed `TaskType` in `backend/app/models`. Every enum that actually lives in `app/models/*.py` today backs a real `Enum(..., native_enum=True)` database column; `TaskType` (Python-only, the plan is never persisted) has no column to back. Placing it there would have broken an otherwise-unbroken convention. **Resolution**: placed it in `backend/app/schemas/daily_plan.py` instead, alongside `MistakeSource` (the same category of purely-service/schema-level enum). This is a location-only deviation — the architectural substance (3-member enum, extensible evaluation loop, zero migration) is unchanged from the plan.

**3.5 — Dashboard integration scope.** The plan's frontend integration note says Daily Plan "replaces those three ad hoc dashboard cards" (Review due / Recommended for you / Continue learning). I replaced the first two (both fully subsumed by Today's Plan's REVIEW/PRACTICE tasks) but kept the hero course-progress card (progress ring, % complete, unit/lesson counts) — Daily Plan's single LESSON task has no equivalent for that visualization, and removing it with no replacement would have been a real regression, not a simplification. Today's Plan still includes a LESSON entry as one more item in its list; the hero card remains a complementary, not redundant, "zoomed out" view.

---

## 4. Tests run and results

**Backend** (`pytest -q`, from `backend/`): **365 passed** (322 pre-existing baseline + 43 new), **0 failed**. `ruff check app/ tests/`: all checks passed. `mypy app/`: no issues found in 104 source files.

New backend test files (43 tests): `test_learner_insight_service.py` (6 — weak-skill sorting/exclusion, improving-skill thresholds at their exact boundaries, insufficient-data check), `test_mistake_notebook.py` (19 — Type A/B grouping incl. the "already-explained-by-Type-B" exclusion, real LESSON/PRACTICE sources via HTTP, user isolation, skill filtering, interleaved-source pagination with no gaps/duplicates, the SHORT_ANSWER-vs-TUTOR discrepancy fix, Practice Again for both target types, cross-user ownership rejection, the abandon-session interaction), `test_daily_plan.py` (7 — task-type restriction, lesson-task selection, review-priority dedup, the exact same-day-then-next-day completion-stability scenario from architecture review item 1, the `local_date` cross-day scenario from item 13), `test_coach.py` (11 — insufficient-data short-circuit, generation+caching, cache-hit-avoids-second-call, malformed-response validation error, Redis-unreachable fail-open, cache invalidation forcing regeneration, the observed_facts/calculated_trends key-omission check via the literal JSON sent to the AI, and 4 real-Redis HTTP endpoint tests including the refresh cooldown's 429).

**Frontend** (`npm test`, from `frontend/`): **79 passed** (70 baseline + 9 new), **0 failed**. `eslint`: 0 problems. `tsc --noEmit`: 0 errors. `next build`: succeeded, `/coach` and `/mistakes` both compiled as static routes.

New frontend tests (9): `coach-api.test.ts` (2), `daily-plan-api.test.ts` (2, incl. `todayLocalDate()`'s local-vs-UTC correctness), `mistakes-api.test.ts` (3), `practiceAgain` cases added to the existing `practice-api.test.ts` (2).

No page-level component tests were added for the 3 new pages. This deliberately follows this codebase's own established, unbroken convention: none of its ~15 existing pages (dashboard, practice, progress, tutor, etc.) have page-level test files — this app tests API-client functions at the unit level and verifies full pages via real browser runs (§5), not component-mounted page tests. Adding page-level tests here would have introduced a pattern inconsistent with every other page in the app.

---

## 5. Real browser / live verification

Performed against the actual running dev stack (`uvicorn` on :8000 with a real Postgres + Redis, `next dev` on :3000), using a real, temporarily-installed Playwright (`npm install --no-save playwright`, removed afterward — `package.json`/`package-lock.json` show no trace of it) driving real Chromium. A fresh user was created via the live signup endpoint; real mistake/practice history was seeded via direct calls to the live API (the same request shapes the backend test suite uses) rather than fighting unknown live-seeded exercise UI, then the actual pages were driven and inspected in the browser.

**Result: 32 of 33 checks passed** on the final run. What was verified:
- Signup → login → dashboard, with the AI Coach card, Mistake Notebook card, and Today's Plan section all rendering.
- The Mistake Notebook showing the real seeded mistakes (3), with a real resolved correct answer displayed for at least one.
- The AI Coach generating a **real** AI-produced insight (a live call to the configured AI provider, not a stub) once the account had real activity, after first confirming a fresh account shows the deterministic insufficient-data message.
- The Coach's Refresh button completing successfully.
- "Practice Again" from a mistake card navigating to `/practice` with a real started session.
- The Daily Plan (checked directly via the live API) showing real completion state after real practice activity.
- Regression spot-check: `/practice`, `/progress`, `/tutor`, `/learn`, `/settings`, `/leaderboard`, `/friends` all still load (HTTP 200) after all V3 changes.
- No 5xx responses anywhere in the run.

**The one remaining "failure"** was 401-status console noise from `POST /api/v1/auth/refresh`, investigated (not dismissed) via the backend request log: it traces to `AuthProvider`'s pre-existing mount-time session-refresh call racing under this script's rapid back-to-back `page.goto()` navigations (far faster than a real user would click) combined with refresh-token rotation. This code path (`frontend/src/lib/auth-context.tsx`) was not touched by V3 and has its own pre-existing test coverage (`auth-context.test.tsx`). Not a V3 regression; not modified, per "no unnecessary changes."

## 6. Accessibility verification

axe-core (`wcag2a`+`wcag2aa` rules) run against `/coach`, `/mistakes`, and `/dashboard` in the real browser session above. **Final result: 0 violations on all three pages.**

The first run found a real violation: 6 `color-contrast` (serious) nodes on `/mistakes`. Root cause: `text-slate-500` used for the "You answered:"/"Correct:" labels (and, found by inspection, the Coach page's `data_note`/refresh-notice text) — a color not used for label/body text anywhere else in this app, which consistently uses `text-slate-400` for that role. Fixed by switching all four occurrences to `text-slate-400`; re-scan confirmed 0 violations.

## 7. Bugs found and fixed

1. **WCAG contrast violation** on `/mistakes` (6 nodes) and latently on `/coach` — `text-slate-500` → `text-slate-400` in both files. Found by axe-core, fixed, re-verified clean.
2. **Coach refresh error handling discarded a good insight on failure.** During verification, a manual refresh hit a real, transient AI-provider failure (a 503 — this app's own designed-for-this exception path, not a crash). The frontend's `catch` block called `setError(...)` on any non-429 failure, which replaced the entire page (including the still-valid, already-displayed insight) with a generic `ErrorState`. Fixed: refresh failures now only ever set an inline `refreshNotice`, never the page-level `error` state — the existing insight stays visible, matching the plan's own requirement ("shown as a disabled state with a clear reason, not a silent no-op or a raw error"). The initial-load failure path (genuinely nothing to show) is unchanged and still shows `ErrorState`.
3. **A test-authoring bug in my own verification helper**, not application code: an early version of `_answer_wrong_via_lesson` reused the same in-progress `LessonAttempt` across repeated calls, silently hitting `submit_answer`'s existing idempotent-resubmission short-circuit instead of recording a second real mistake. Fixed before any test was reported as passing (see the helper's own docstring in `test_mistake_notebook.py`).

No other bugs were found. All fixes above were verified by re-running the relevant automated checks and, for the two application-code bugs, by re-running the real-browser verification and observing the fix take effect (32/33 → confirmed on the corrected run, with 0 axe violations and a clean refresh).

## 8. Known remaining limitations (honest, not implemented)

Everything below was either explicitly out of scope per the plan or is a genuine, disclosed gap — nothing here was silently dropped.
- **No `DetectedError.corrected_text` column.** Tutor-sourced mistakes in the Mistake Notebook show `correct_text: null`, honestly, because `conversation_service._record_correction` never persists the AI's `corrected` field anywhere (confirmed in the original audit). The plan explicitly scoped adding this column as a *documented future option*, not part of V3.
- **No true mastery-over-time chart anywhere** (pre-existing limitation, not new to V3) — `SkillMastery` is a snapshot with no history table.
- **Daily Plan has exactly one LESSON task, from one course.** If a learner is ever enrolled in multiple courses, only the first (by title, then unit/lesson position) incomplete lesson across all of them is surfaced — matches the current single-course reality of this app's seed data and every other single-course assumption already baked into `course_repository.get_skill_by_code`'s own comment.
- **No fine-grained confidence signals, no learner-goal input to Coach/Daily Plan/Mistake Notebook** — both were audited in the original plan and confirmed absent from the schema; neither was fabricated here.
- **No V3.4 Next Best Action Engine** — not in scope; only the `TaskType` extensibility seam and the shared `learner_insight_service` layer exist as the preparation the plan called for.

## 9. Git status (unchanged by this phase — nothing committed, nothing pushed)

```
 M backend/app/api/deps.py
 M backend/app/api/v1/me.py
 M backend/app/api/v1/practice.py
 M backend/app/core/rate_limit.py
 M backend/app/models/evaluation.py
 M backend/app/models/practice.py
 M backend/app/models/progress.py
 M backend/app/repositories/evaluation_repository.py
 M backend/app/repositories/learner_model_repository.py
 M backend/app/schemas/practice.py
 M backend/app/services/lesson_service.py
 M backend/app/services/practice_service.py
 M frontend/src/app/(app)/dashboard/page.tsx
 M frontend/src/app/(app)/practice/page.tsx
 M frontend/src/app/(app)/progress/page.tsx
 M frontend/src/lib/__tests__/practice-api.test.ts
 M frontend/src/lib/practice-api.ts
?? V3_ADAPTIVE_INTELLIGENCE_AUDIT.md
?? V3_FINAL_REVIEW_PACKAGE.md
?? V3_IMPLEMENTATION_REPORT.md
?? V3_REVISED_IMPLEMENTATION_PLAN.md
?? backend/app/repositories/mistake_repository.py
?? backend/app/schemas/coach.py
?? backend/app/schemas/daily_plan.py
?? backend/app/schemas/mistakes.py
?? backend/app/services/coach_service.py
?? backend/app/services/daily_plan_service.py
?? backend/app/services/learner_insight_service.py
?? backend/app/services/mistake_service.py
?? backend/tests/test_coach.py
?? backend/tests/test_daily_plan.py
?? backend/tests/test_learner_insight_service.py
?? backend/tests/test_mistake_notebook.py
?? frontend/src/app/(app)/coach/
?? frontend/src/app/(app)/mistakes/
?? frontend/src/lib/__tests__/coach-api.test.ts
?? frontend/src/lib/__tests__/daily-plan-api.test.ts
?? frontend/src/lib/__tests__/mistakes-api.test.ts
?? frontend/src/lib/coach-api.ts
?? frontend/src/lib/daily-plan-api.ts
?? frontend/src/lib/mistakes-api.ts
?? frontend/src/lib/reason-label.ts
?? frontend/src/types/coach.ts
?? frontend/src/types/daily-plan.ts
?? frontend/src/types/mistakes.ts
```

No `alembic/versions/` entries — confirming zero migrations, as designed. No `package.json`/`package-lock.json` changes from the temporary Playwright install (installed with `--no-save`, then `npm uninstall`led).
