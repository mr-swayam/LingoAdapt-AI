# Release Candidate Report — AI Language Learning Tutor

**Phase 13: Release Candidate & Product Validation**
Date: 2026-08-19
Scope: validate the existing product (Phases 0–12, all previously implemented) as a real, usable language-learning application. No new features were added — every change in this phase is either a verification, a bug fix found by verification, or a test.

Every result below was produced by actually executing the corresponding check against the real backend (Postgres + Redis + real Groq API), the real frontend (Next.js dev build, real browser via Playwright), or the real test suite. Nothing in this report is inferred or assumed.

---

## 1. System status

| Component | Status |
|---|---|
| Backend (FastAPI) | Healthy. 289/289 tests passing, `ruff` clean, `mypy` clean (95 source files). |
| Frontend (Next.js) | Healthy. 49/49 tests passing, `eslint`/`tsc --noEmit` clean, production build succeeds (16 routes). |
| Database (Postgres) | Healthy. 29 tables, migrations verified reproducible from an empty database with **zero drift** between models and migration history. |
| Redis | Healthy, in active use since Phase 12 (rate limiting). Confirmed this environment's local Redis is v5.x (pre-RESP3) — the app pins `protocol=2` to match it; this is a note for whoever deploys, not a defect. |
| AI provider (Groq) | Reachable, configured, real calls succeed. Latency/error-rate logging (Phase 11) confirmed live in this phase (real `groq_chat_completed` log lines observed). |
| Deployment target | **None exists.** This is a fully-built, fully-verified *local* application. See §9 Launch Blockers. |

---

## 2. Test results

- Backend: `pytest -q` → **289 passed**, 0 failed. `ruff check .` → clean. `mypy app` → clean (95 files).
- Frontend: `vitest run` → **49 passed**. `eslint .` → clean. `tsc --noEmit` → clean. `next build` → succeeds, all 16 routes build (static + dynamic as expected).
- New tests added this phase: `test_evaluation_schema.py` (18 tests — direct Pydantic-level validation of AI evaluation output: boundary scores, missing/extra/wrong-typed fields, error-category normalization), `test_failure_scenarios.py` (2 tests — database failure mid-write, oversized audio upload), plus additions to `test_short_answer.py` (5 parametrized tests, one per AI error category) and `test_observability.py` (4 tests for the new CORS production-safety check).
- Migration reproducibility: a fresh, empty Postgres database (`lingoadapt_clean_migration_test`) was created, `alembic upgrade head` run against it from scratch (all 12 migrations applied cleanly), then `alembic revision --autogenerate` was run against the result — the generated migration body was **empty** (`pass`/`pass`), confirming the SQLAlchemy models and the migration chain are in exact agreement. Test database and throwaway migration file were removed afterward.

---

## 3. Accessibility status

Full automated audit (Playwright + axe-core, temporarily installed) across all 13 distinct pages in the app, both logged-out and logged-in (learner and admin).

**Before this phase**: 1 outstanding violation (`color-contrast`, serious) on a disabled button, carried over from Phase 12's audit.

**Investigation** (per instruction, not suppressed without determining legitimacy): traced the violation through several dead ends (it appeared inconsistently on different pages across repeated scans) before finding the real, deterministic cause — `PrimaryButton`'s "secondary" style variant (used for Log out, Add language, Cancel, Decline, Validate, and 7 other buttons across 7 files) was implemented by passing a `className` override (`bg-slate-800 text-slate-200`) that was supposed to beat the component's own base classes (`bg-cyan-500 text-slate-950`). It didn't, reliably — Tailwind resolves same-property utility-class conflicts by where each class is declared in the *compiled stylesheet*, not by where it appears in the `className` string, so `text-slate-950` (the base) was silently winning over `text-slate-200` (the intended override) on every one of those 12 buttons, everywhere in the app, all the time — not just when disabled. Direct `getComputedStyle` inspection confirmed dark-on-dark, near-invisible text on both the flagged button (Dashboard's "Log out") and an unflagged one (Admin's "Add language" button, only unflagged because it lives inside a collapsed `<details>` that axe correctly excludes from visibility checks — meaning the real blast radius was larger than the automated scan alone showed).

**Fix**: `PrimaryButton` now takes a `variant` prop (`primary`/`secondary`/`danger`), each a complete, non-conflicting class set. All 12 call sites updated.

**Re-scan after fix**: **13/13 pages, 0 violations.** Confirmed additionally via direct browser inspection (not just axe) that the previously-broken buttons now render with correct, legible colors, and via real screenshots taken during the Task 10 smoke test (Dashboard's "Log out" button and a disabled "Check" button both clearly legible in both desktop and mobile viewports).

| Finding | Classification |
|---|---|
| Disabled-button/secondary-button text-color bug (12 buttons, 7 files) | **HIGH** before fix → **NO ISSUE** after fix (verified) |

---

## 4. Security status

- **Secrets**: repo-wide grep for the project's real Groq API key prefix (`gsk_`) → no matches outside the gitignored `backend/.env`. `.env.example` contains only placeholders. No hardcoded credentials found in `app/` or `src/` (targeted grep for `password=`/`secret=`/`token=`/`api_key=` literals). **NO ISSUE.**
- **Production config fail-fast**: `Settings` already refused to start with the default placeholder `SECRET_KEY` when `ENVIRONMENT=production` (Phase 12). This phase found and fixed a gap in the same mechanism: **there was no equivalent check for CORS** — a production deploy that forgot to set `CORS_ORIGINS` would have silently run with `http://localhost:3000` as its only allowed origin, which would either lock out the real frontend or (if someone "fixed" it by allowing `*`) open the API to any origin. Extended the existing `model_validator` to also reject `localhost`/`127.0.0.1` origins when `ENVIRONMENT=production`; both branches (secret key, CORS) now share one validator and are both tested (`test_observability.py`).
- **Authentication**: bcrypt (SHA-256 pre-hashed to sidestep the 72-byte limit) for passwords, HS256 JWTs with a 15-minute access-token lifetime, refresh tokens stored only as a hash, `secure` cookie flag correctly conditioned on environment. Reviewed, unchanged, still sound.
- **Rate limiting**: confirmed enabled and enforced with real, live 429s (not just unit-tested) — 10/minute per IP on auth endpoints, 30/hour per user on every AI-touching endpoint (enforced centrally in `get_metered_ai_provider`, so no route can forget it).
- **AI cost controls**: enabled — the above rate limit, plus a length cap on free-form answers (2000 chars) added in Phase 12 to stop an unbounded string from reaching a paid AI call.
- **SQL injection**: reviewed — every query goes through SQLAlchemy's query builder; no raw string-interpolated SQL found anywhere in the backend.
- **Dependency vulnerability scan**: **not performed** — no scanner (`pip-audit`, `npm audit` against a live advisory feed, or equivalent) is configured in this environment, and fabricating a scan result would violate this project's own rule against inventing verification. This is a real gap, not a clean bill of health.

| Finding | Classification |
|---|---|
| Missing production CORS fail-fast | **MEDIUM** before fix → **NO ISSUE** after fix (added + tested) |
| No dependency vulnerability scan performed | **MEDIUM** (unknown, not "clear" — should be run before any public launch) |
| Everything else reviewed above | **NO ISSUE** |

---

## 5. AI evaluation results

A 15-case deterministic dataset was run through the real `evaluate_free_response()` service function against the live Groq API (not mocked), covering every category requested: correct answers, grammar errors, spelling errors, multiple valid phrasings, natural/casual language variation, a vocabulary false-friend error, off-topic content, beginner/intermediate/advanced responses, empty input, gibberish, and three translation-specific cases (correct, wrong-meal, wrong-verb).

**Quality observed** (full transcript retained in this session, not reproduced verbatim here):
- Correctly accepted paraphrases and idiomatic/casual rewordings that used different vocabulary than the model answer ("hop out of bed, hit the shower, grab a quick bite" — scored 0.96, correct) — confirms the evaluator isn't doing rigid exact-match under the hood.
- Correctly rejected off-topic content (score 0.0) and gibberish, with an on-topic corrective explanation rather than a confused response.
- Correctly identified and classified grammar errors (verb form, missing article), spelling errors (with accurate corrections for every misspelled word), and a vocabulary false-friend ("douche" for "shower") as `VOCABULARY`, not `GRAMMAR` or `SPELLING`.
- Correctly distinguished two different translation-error subtypes (wrong noun vs. wrong verb) with accurate, specific explanations referencing the source-language word.
- Did not penalize the advanced/sophisticated response for complexity, and correctly flagged the beginner response's missing content (no shower step) while still crediting what it got right — reasonable calibration across skill levels.
- **One real reliability data point**: on the first attempt at the `spelling_error` case, the model returned JSON missing the required `explanation`/`corrected_answer` fields. `RawAIEvaluation`'s schema validation correctly rejected it (`AIResponseValidationError`) rather than accepting a broken result — the safety net rules.md requires ("never trust AI output without validation") worked exactly as designed. A retry succeeded. This happened once in this session's ~18 real evaluation calls across Phase 13 (≈5–6%); too small a sample to state a reliable failure rate, but real evidence this isn't a zero-probability event.

| Finding | Classification |
|---|---|
| AI evaluation quality across all 12 tested categories | **NO ISSUE** — consistently good judgment observed |
| Occasional AI schema-validation failures (model omits required fields) | **MEDIUM** — not a data-safety risk (the validator catches it and nothing is written), but a learner hitting it sees a 503 and must retry; worth monitoring via `ai_call_logs` in production to see the real rate at scale |

---

## 6. Adaptive-learning verification

Two synthetic learners were created via the real signup API and driven through real, repeated lesson attempts (not seeded directly in the database) with intentionally opposite performance:

- **Learner 1**: 3 attempts answering GREETINGS exercises incorrectly, 3 attempts answering INTRODUCTIONS exercises correctly.
- **Learner 2**: the exact inverse.

Resulting mastery (`GET /me/mastery`, real values):
- Learner 1 — GREETINGS: **0.0**, INTRODUCTIONS: **45.4**
- Learner 2 — GREETINGS: **63.2**, INTRODUCTIONS: **0.0**

Both learners' weak-skill mastery landed at exactly 0.0 (repeated wrong answers) and their strong-skill mastery diverged upward — a clean, correctly-inverted signal.

Personalized practice (`POST /practice/start`) for each learner was then checked for both skill coverage and **priority order** (the real adaptive signal — `recommendation.py`'s `compute_skill_priority` ranks by weakness first; with only 2 candidate skills per learner, the *set* returned is necessarily the same for both, so set-membership alone isn't a meaningful divergence check — order is):

- Learner 1's first practice exercise targeted **GREETINGS** (their real weak skill).
- Learner 2's first practice exercise targeted **INTRODUCTIONS** (their real weak skill).

**10/10 checks passed**, including the specific claim Phase 5's exit criteria requires ("two users with different histories can receive different practice sets") — verified with real, opposite histories producing real, opposite prioritization.

| Finding | Classification |
|---|---|
| Adaptive/recommendation engine | **NO ISSUE** — verified working as designed with real divergent data |

---

## 7. Performance results

- Load test (`tools/load_test.py`, `GET /courses`, local machine, local Postgres): concurrency 20/200 requests → 249 req/s, p50 64ms, p95 200ms, p99 213ms, 0 errors. Concurrency 50/500 requests → 272 req/s, p50 172ms, p95 219ms, p99 270ms, 0 errors. Latency scales up gracefully (not catastrophically) with load; no errors at either level.
- This is a **single-machine, local-database sanity check**, not a production-capacity claim — no real network hop, no connection pooling under real concurrent load, no real production Postgres tier.
- Query-pattern audit: every nested-relationship read in the repository layer already uses `selectinload`/`joinedload` consistently — no N+1 patterns found.
- Migration/index audit: Phase 11's analytics queries filter several tables by date range; Phase 12 added the 4 indexes those queries needed (`learning_events.created_at`, `detected_errors.created_at`, `lesson_attempts.started_at`, `practice_sessions.started_at`) — confirmed still present and applied.

| Finding | Classification |
|---|---|
| Local load test results | **NO ISSUE** for current scope; informational only |
| No production-scale load test performed | **LOW** — there is no production environment to test against yet |

---

## 8. Known issues

Full inventory, most-significant first. Anything already resolved during this phase is listed with its pre-fix and post-fix classification for traceability.

| # | Issue | Classification | Status |
|---|---|---|---|
| 1 | `PrimaryButton` secondary/danger variants had broken (near-invisible) text color on 12 buttons across 7 files | HIGH → **NO ISSUE** | Fixed + verified (§3) |
| 2 | Missing production CORS fail-fast validation | MEDIUM → **NO ISSUE** | Fixed + tested (§4) |
| 3 | No dependency vulnerability scan has ever been run | **MEDIUM** | Open — no scanner available in this environment |
| 4 | Occasional AI schema-validation failures surface as a learner-visible 503/retry | **MEDIUM** | Open — safety net works correctly; real-world frequency unknown at scale |
| 5 | No real external error-tracking service (Sentry or equivalent) connected | **MEDIUM** | Open — structured logging + request-ID correlation (Phase 12) is the foundation such a service would plug into; no account exists to wire up for real |
| 6 | Backup strategy has a tested mechanism but no schedule or production host to run it on | **LOW** | Open — `tools/backup-postgres.ps1`/`restore-postgres.ps1` verified via a real backup→restore→row-count-diff drill (Phase 12) |
| 7 | Rate limits (10/min auth, 30/hour AI) are reasonable defaults, not tuned against real traffic | **LOW** | Open — no real traffic exists yet to tune against |
| 8 | `docker-compose.yml` path untested in this environment (Docker Desktop's daemon doesn't start here) | **LOW** | Open — Postgres/Redis fully verified via the native setup instead |
| 9 | Admin analytics dashboard has no date-range picker or CSV export | **LOW** | Open — noted as a Phase 11 limitation, not revisited this phase |
| 10 | No bulk content import, drag-and-drop reordering, or media upload in the admin course editor | **LOW** | Open — noted as a Phase 10 limitation, not revisited this phase |
| 11 | A fresh learner's `/me/review` list is empty immediately after their first lesson | **NO ISSUE** | Expected behavior — spaced repetition has nothing due immediately after first exposure; confirmed correct, not a bug (§2 of the E2E flow) |
| 12 | Single shared Groq API key/account for all users | **LOW** (for a closed beta) | Open — fine for a small closed beta; would need real usage-based planning before a larger launch |

---

## 9. Launch blockers

**No blocking defects were found in the application itself.** Every code-level finding above is MEDIUM or lower, and the two most significant issues found this phase (the button-contrast bug and the missing CORS validation) were fixed and re-verified before this report was written.

The actual blocker to starting a closed beta is **operational, not code-quality**: this application has never been deployed anywhere. Concretely, before real users can be invited:

1. **A production hosting target must exist** — a server or platform for the FastAPI backend, a managed or self-hosted Postgres instance, a Redis instance, and a hosting target for the Next.js frontend. None of this is provisioned; everything verified in this report ran against `localhost`.
2. **A real `SECRET_KEY` and `CORS_ORIGINS`** must be set for that environment (the app will now refuse to start without them, per §4 — this is enforced, not just documented).
3. **A real domain and TLS** for the frontend origin, matching whatever `CORS_ORIGINS` is set to.
4. **A decision on error-tracking and dependency scanning** (§8, items 3 and 5) — not hard blockers for a *small, trusted* closed beta, but should happen before wider release.

None of the above can be verified from this local environment — they require an actual deployment target to exist first, which is out of scope for "prove the product works" and was correctly excluded from this phase's task list.

| Finding | Classification |
|---|---|
| No production deployment target exists | **BLOCKER** (for launch — not for code readiness) |

---

## 10. Recommended next steps

1. Provision a real hosting target (backend + Postgres + Redis + frontend) and deploy this exact, verified codebase to it.
2. Set real `SECRET_KEY`, `CORS_ORIGINS`, and (if going beyond a handful of trusted testers) a dedicated Groq API key/plan for production traffic, separate from the development key used throughout this session.
3. Run a dependency vulnerability scan (`pip-audit`, `npm audit`, or a hosted equivalent) against the pinned versions in `pyproject.toml`/`package.json` before the beta opens.
4. Wire up a real error-tracking service using the request-ID-correlated structured logging already in place (Phase 12) — no code changes needed beyond configuration once an account exists.
5. Put `tools/backup-postgres.ps1` on an actual schedule against the production database once it exists.
6. Once a small closed beta is running, use `GET /admin/analytics/overview` (Phase 11) and the `ai_call_logs` table (Phase 11/12) to monitor real AI error rate and latency — this is exactly the data needed to turn the "occasional schema-validation failure" finding (§5) from a small-sample observation into a real, actionable number.
7. Revisit rate-limit values (§8, item 7) once real usage patterns exist.

**Overall assessment: the product is functionally complete, extensively verified end-to-end (including the adaptive-learning engine's actual behavior with divergent synthetic histories, not just its code), and has no known code-level blocker. It is ready for a closed beta as soon as a deployment target exists.**
