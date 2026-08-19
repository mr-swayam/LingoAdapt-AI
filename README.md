# AI Language Learning Tutor

A Duolingo-inspired language-learning platform with a persistent learner model and an adaptive AI tutor. Built as a modular monolith: Next.js frontend, FastAPI backend, PostgreSQL for state, Redis for cache/jobs.

See [`project_requirement_document.md`](./project_requirement_document.md), [`architecture.md`](./architecture.md), [`rules.md`](./rules.md), [`phases.md`](./phases.md), [`design.md`](./design.md), and [`memory.md`](./memory.md) for the full product, architecture, and engineering spec. These documents are the source of truth for this project.

## Current status

**Phase 12 — Production Hardening** is complete. This was the final phase in `phases.md`. See [Phase 12 notes](#phase-12-notes) below ([Phase 11](#phase-11-notes), [Phase 10](#phase-10-notes), [Phase 9](#phase-9-notes), [Phase 8](#phase-8-notes), [Phase 7](#phase-7-notes), [Phase 6](#phase-6-notes), [Phase 5](#phase-5-notes), [Phase 4](#phase-4-notes), [Phase 3](#phase-3-notes), [Phase 2](#phase-2-notes), [Phase 1](#phase-1-notes), and [Phase 0](#phase-0-notes) notes further down).

## Project layout

```text
frontend/    Next.js 16 + TypeScript + Tailwind CSS + Framer Motion
backend/     FastAPI + SQLAlchemy + Alembic + PostgreSQL
docker-compose.yml   Local Postgres + Redis
```

## Prerequisites

- Node.js 20+
- Python 3.12+ (developed against 3.14)
- PostgreSQL 16+ and Redis, reachable locally. Two ways to get them:
  - **Docker**: `docker compose up -d` (spins up Postgres 16 + Redis 7 per `docker-compose.yml`).
  - **Native (used in this session, since Docker Desktop wouldn't start here)**: install Postgres directly (e.g. `winget install PostgreSQL.PostgreSQL.17`) and run `tools/start-redis-windows.ps1` for a portable Redis server that needs no admin rights. See [Local database setup](#local-database-setup) below for details.

## Getting started

### 1. Start Postgres and Redis

```bash
docker compose up -d
```

If you're on native Postgres instead, make sure the `postgresql-x64-*` service is running and that a `lingoadapt` role/`lingoadapt_dev` database exist (see below).

### 2. Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate       # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -e ".[dev]"
cp ../.env.example .env        # then edit values as needed
uvicorn app.main:app --reload --port 8000
```

Backend will be available at http://localhost:8000. Interactive API docs at http://localhost:8000/docs.

Run migrations:

```bash
alembic upgrade head
```

Seed the demo course (idempotent - safe to re-run):

```bash
python -m app.seed
```

Run tests / lint / type-check:

```bash
pytest -q
ruff check .
mypy app
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:3000.

Run tests / lint:

```bash
npm run test
npm run lint
```

## Environment variables

See [`.env.example`](./.env.example) for the full list. Copy it to `backend/.env` (backend) and set `frontend/.env.local` (frontend) — both are gitignored. Never commit real secrets.

**AI provider** (needed starting Phase 6): set `AI_PROVIDER=groq`, `AI_API_KEY=<your Groq API key>`, and `AI_DEFAULT_MODEL=openai/gpt-oss-120b` (or another chat-completion model from your Groq account — check `GET https://api.groq.com/openai/v1/models` with your key for what's currently available) in `backend/.env`. Without a configured key, `AI_PROVIDER` defaults to `none` and any SHORT_ANSWER exercise submission returns a clean `503 "AI evaluation is not configured on this server"` rather than crashing — the rest of the app (lessons, practice, mastery, gamification) works fully without it.

## Local database setup

This machine already had a native PostgreSQL 17 install (Windows service `postgresql-x64-17`, port 5432) with a pre-existing `lingoadapt` database from earlier work on this project — a full 34-table schema unrelated to the fresh backend built in this session. **That database was left untouched.** Instead, a separate `lingoadapt_dev` database was created for this codebase:

```sql
CREATE ROLE lingoadapt WITH LOGIN PASSWORD 'lingoadapt';   -- already existed
CREATE DATABASE lingoadapt_dev OWNER lingoadapt;           -- created fresh, empty
```

`backend/.env`, `.env.example`, and `docker-compose.yml` all point at `lingoadapt_dev`. If you want to work with the original `lingoadapt` database's schema/data instead, that needs an explicit decision — don't just repoint the connection string, since the two schemas don't match.

A third database, `lingoadapt_dev_test` (same role), is used exclusively by the backend's pytest suite (see `backend/tests/conftest.py`) — tables are created/dropped per test session and each test runs in a rolled-back transaction, so it never accumulates data.

### Redis

A Windows Redis/Memurai installer needs admin elevation, which this automated session doesn't have. Instead, `tools/start-redis-windows.ps1` downloads a portable Redis-for-Windows build (no install, no elevation — just run it) and starts `redis-server` in the foreground:

```powershell
./tools/start-redis-windows.ps1
```

It listens on `redis://localhost:6379/0`, matching `REDIS_URL` in `.env.example`. Leave it running in its own terminal while developing; it's not registered as a Windows service, so it won't survive a reboot or auto-start — rerun the script when needed.

**Compatibility note:** this build is Redis 5.0.14 (2022), which predates the RESP3 protocol. Modern `redis-py` (5.x+) defaults to a `HELLO`-based handshake that this server doesn't understand, and fails with `unknown command 'HELLO'`. Construct clients with `protocol=2` to force the older RESP2 handshake, e.g. `redis.from_url(REDIS_URL, protocol=2)`. Apply this wherever a Redis client gets wired up in later phases (background jobs, caching). A managed cloud Redis in production won't need this — it's specific to this local dev binary.

## Phase 12 notes

This was the final phase (`phases.md`'s exit criteria: "the application is deployable and maintainable in production"). It touches ten different concerns rather than building one feature, so this section is organized by task instead of chronologically.

### Security review

- **Startup fail-fast on a misconfigured production secret** (`app/core/config.py`): `Settings` now has a `model_validator` that raises if `ENVIRONMENT=production` and `SECRET_KEY` is still the placeholder default - `app.core.security` signs every access token with this key, so shipping the default would mean anyone could forge a valid token. `get_settings()` is called at import time in `main.py`, before the FastAPI app object even exists, so a misconfigured production start fails immediately rather than silently issuing forgeable tokens.
- **AI cost/injection guard on free-form answers** (`app/services/ai_grading.py`): `AnswerSubmitRequest.submitted_answer` is an untyped `dict[str, Any]` (schemas/course.py) - nothing capped the length of a SHORT_ANSWER's `text` field before it was interpolated straight into a paid Groq prompt. Added a 2000-character cap (matching the existing cap on tutor conversation turns) that raises `GradingError` (mapped to a 400) before the AI call, not after.
- **Password hashing, JWT handling, and refresh-token storage were already solid** (bcrypt with a SHA-256 pre-hash workaround for bcrypt's 72-byte limit, HS256-signed short-lived access tokens, refresh tokens stored only as a hash) - reviewed, no changes needed.
- **SQL injection surface**: reviewed - every query in every repository goes through SQLAlchemy's query builder; grepped the whole backend for raw string-interpolated SQL and found none.
- **Audio upload size limits** (Phase 8's `speech_service.MAX_AUDIO_BYTES = 10MB`) - reviewed, already in place.
- Dependency vulnerability scanning against a live CVE database wasn't done - this environment has no such scanner configured, and fabricating a scan result would violate this project's own rule against fabricating verification. Documented as a follow-up instead (see Known limitations).

### Rate limiting + AI cost controls

Both share one new primitive: `app/core/rate_limit.py`'s `check_rate_limit()`, a fixed-window counter on Redis (`INCR` + `EXPIRE` on first use) - the first thing in this codebase to actually use Redis, which `architecture.md` provisions for "cache/jobs" but nothing had touched until now. It fails **open** (allows the request, logs a warning) if Redis is unreachable - defense-in-depth shouldn't take the app down over its own backing store.

Two gates, both in `app/api/deps.py` as their own overridable dependencies (mirroring how `FakeAIProvider` is swapped in for tests) rather than inlined per-route:
- `auth_rate_limit_gate` - 10 requests/minute per IP, applied to `POST /auth/signup` and `POST /auth/login`. Blunts credential-stuffing and signup-spam scripts.
- `ai_rate_limit_gate` - 30 calls/hour per user, folded directly into `get_metered_ai_provider` (Phase 11's AI-call wrapper) so **every** AI-touching route is covered automatically, with no router able to forget it. A caller past the limit gets a 429 before the (billed) provider is ever reached.

`tests/conftest.py`'s shared `client` fixture overrides both gates to `None` (a no-op), the same way it swaps in `FakeAIProvider` - otherwise the hundreds of signups and AI calls the rest of the test suite makes would trip real Redis-backed limits and fail unrelated tests. `tests/test_rate_limiting.py` builds its own TestClient *without* that override specifically to drive real requests past both limits and confirm a real 429.

### Logging + error monitoring

Phase 11's investigation found that `app.ai`'s `logger.info`/`logger.warning` calls (Groq latency, transient errors) had nowhere configured to write to - the root logger was never touched anywhere in the app. `app/core/logging_config.py` fixes that with a `dictConfig` call at import time in `main.py` (`INFO` in non-development, `DEBUG` in development), quieting `httpx`/`httpcore`'s own verbose logging so it doesn't drown out the app's lines - confirmed necessary live, not assumed (see below).

`app/core/middleware.py`'s `RequestLoggingMiddleware` adds a short id to every request (returned as `X-Request-ID`, usable to correlate a user's bug report with server logs), and logs a `request_completed`/`request_failed` line with method, path, status, and duration for every request. Paired with a global `@app.exception_handler(Exception)` in `main.py` that logs the full traceback (with the same request id) and returns a clean `{"detail": "Internal server error.", "request_id": ...}` body instead of Starlette's bare default or a leaked stack trace.

This is the app's error-monitoring *foundation*, not a live external service - no Sentry/Rollbar account exists for this project, and this project's own rules explicitly forbid inventing credentials or external-service integrations. A real service could subscribe to these same structured log lines later.

### Database backup strategy

`tools/backup-postgres.ps1` (`pg_dump`, custom format, timestamped into `tools/backups/` - gitignored, dumps may contain real user data) and `tools/restore-postgres.ps1` (`createdb` + `pg_restore --clean --if-exists`), matching the PowerShell-script convention `tools/start-redis-windows.ps1` already established for this Windows dev environment. Both locate `pg_dump`/`pg_restore`/`createdb` on PATH or fall back to scanning `C:\Program Files\PostgreSQL\*\bin`.

A production deployment would run the backup script on a schedule (daily, via cron/Task Scheduler/a managed provider's built-in backup feature) with a retention window (e.g. 7 daily + 4 weekly) - this repo provides the mechanism, not a scheduler, since there's no production host to schedule it on yet.

### Performance optimization

- **Added 4 missing indexes** (migration `cc2e1c228aea`): `learning_events.created_at`, `detected_errors.created_at`, `lesson_attempts.started_at`, `practice_sessions.started_at`. Phase 11 added heavy date-range-filtered queries against exactly these columns (`analytics_repository`'s daily-active-user/retention/completion/mistake queries) with no supporting index - a real gap in Phase 11's own work, caught while reviewing query patterns for this phase.
- **Audited the repository layer for N+1 queries**: every nested-relationship read (course → units → lessons → exercises → options, etc.) already uses `selectinload`/`joinedload` consistently (`app/repositories/course_repository.py` and others) - no changes needed here, but worth confirming rather than assuming, since it's exactly the kind of thing that silently rots.
- **Load testing** (`tools/load_test.py` - `asyncio` + `httpx`, both already dependencies, rather than pulling in a dedicated framework for a one-off local check): run against `GET /courses` on this single dev machine. At concurrency=20/200 requests: 249 req/s, p50 64ms, p95 200ms, p99 213ms, 0 errors. At concurrency=50/500 requests: 272 req/s, p50 172ms, p95 219ms, p99 270ms, 0 errors. Not a production-scale claim (one machine, local Postgres, sync SQLAlchemy sessions running through FastAPI's thread pool) - a sanity check that the app holds up under realistic concurrency and degrades gracefully (not catastrophically) as load increases, which it does.

### Accessibility audit + mobile QA

Ran a real automated audit (Playwright + axe-core, installed temporarily) against all 13 distinct pages in the app (both logged-out and logged-in, learner and admin) rather than a manual pass. Two real, systemic bugs surfaced - not fabricated, not assumed:

**The entire app was rendering with a broken dark theme whenever the browser's OS-level color-scheme preference wasn't "dark."** `globals.css` still had `create-next-app`'s default light/dark boilerplate (`body { background: var(--background); color: var(--foreground); }`, toggled by a `prefers-color-scheme` media query) - written as *plain, unlayered* CSS. Tailwind v4 emits its own utility classes (including this app's actual `bg-slate-950 text-slate-100` on `<body>` in `layout.tsx`) inside `@layer utilities`, and per the CSS Cascade Layers spec, **any unlayered rule beats a layered one on the same element, regardless of specificity or source order.** So the leftover boilerplate silently won every time, and the real theme classes never took effect unless the browser happened to prefer dark mode. This was caught by directly checking `getComputedStyle(document.body).backgroundColor` (`rgb(255, 255, 255)` - literal white) after axe's contrast checker reported nonsensical fully-white background colors on every single page; a plain screenshot at that point showed the landing page's heading and buttons nearly invisible against a white background. Confirmed *not* a stale-cache artifact by fully deleting `.next` and restarting before diagnosing further. Fixed by deleting the entire leftover block from `globals.css` - this app has one deliberate dark theme, not a light/dark toggle, so Tailwind's utilities are now the only thing controlling body's colors. Re-verified with a fresh screenshot (correct near-black background, legible text) and a full audit re-run.

**`text-slate-500`/`text-slate-600` (used across 18+ files as the standard "secondary/fine-print text" color) fails WCAG's 4.5:1 contrast ratio against this app's dark backgrounds** (measured 3.44-4.23:1, computed via the same relative-luminance formula axe uses, confirmed against axe's own reported ratios) - close enough to pass a casual glance but a real, systemic failure once the background-color bug above was fixed and contrast could be measured correctly. `text-slate-400` clears 7-7.9:1 against the same backgrounds (verified before the bulk edit, not after), so every occurrence of `text-slate-500`/`text-slate-600` used as text color was swapped to `text-slate-400`.

Beyond those two systemic fixes: added a `<main>` landmark in the root layout (fixed `landmark-one-main`/`region` violations on every page at once); gave the shared `ProgressBar` component (used on the dashboard, quest cards, and skill-mastery bars) an `aria-label`, since a `role="progressbar"` with no accessible name is a real screen-reader dead end; removed `AchievementCard`'s `opacity-60` on locked achievements, which combined with already-dim text to collapse contrast on that specific element even after the text-color fix (the locked/earned distinction is already conveyed by border and icon color, so the opacity reduction was redundant *and* harmful); added a screen-reader-only `<h1>Practice</h1>` to every render branch of `/practice` (it previously only had an `<h1>` on the "session complete" screen). Left one PLAUSIBLE (not necessarily needing a fix) finding: `PrimaryButton`'s disabled state has low contrast (WCAG 1.4.3 explicitly exempts inactive/disabled UI components from the contrast requirement, so this is a reviewed, accepted finding, not an oversight).

**Mobile QA**: same logged-in sessions, re-driven at a 390×844 (iPhone 12) viewport across dashboard, learn, practice, admin, and admin analytics. All five reflow correctly - card grids collapse to fewer columns, no horizontal overflow, text stays legible, buttons stay reachable. No mobile-specific bugs found (the desktop-first Tailwind classes throughout the app already use relative units and flex/grid layouts that happen to work at this width).

### Verification performed

- Backend: `pytest -q` - 246 passed (28 new since Phase 11: `test_rate_limiting.py` - unit tests against a fake Redis client plus two true end-to-end tests that drive real requests past both limits and confirm a real 429; `test_observability.py` - request-id header presence, a monkeypatched unhandled exception producing a clean non-leaking 500 body, and `Settings` validation for all three environment/secret-key combinations; one new test in `test_short_answer.py` for the length guard). `ruff check .` and `mypy app` clean (95 source files).
- Migrations `45e2477bc564` (Phase 11's `ai_call_logs`, already applied) and `cc2e1c228aea` (this phase's 4 indexes) both applied and verified against the live dev database.
- **Real, live-fired proof, not just passing tests**: hit `GET /courses` at concurrency 20 and 50 against the actual running server and got real latency numbers (above); triggered a real Groq call and watched `app.ai groq_chat_completed model=... latency_ms=950 ...` print to the console for the first time ever in this project, closing the exact gap Phase 11 found; ran the backup script against the real `lingoadapt_dev` database, then restored the resulting dump into a fresh `lingoadapt_restore_drill` database and diff-checked row counts across 7 tables (all matched exactly) before dropping the drill database; discovered live that this environment's portable Redis is version 5.x (`tools/start-redis-windows.ps1`), which predates RESP3/`HELLO` - `redis-py`'s default protocol negotiation failed against it with `unknown command 'HELLO'` until `check_rate_limit`'s client was pinned to `protocol=2`.
- Frontend: `npx vitest run` - 49 passed (1 new: `getAnalyticsOverview`'s admin-api client test, actually added at the tail end of Phase 11 - no new frontend logic needed new tests this phase, since every change was a class-name/markup/CSS fix, not new behavior). `npx eslint .` and `npx tsc --noEmit` clean, `npm run build` succeeds (unchanged route list).
- All verification accounts (`ratelimit*@example.com`, `ai-ratelimit@example.com`, `phase12logcheck@example.com`, `a11y-learner@example.com`, `a11y-admin@example.com`) and any stray `ai_call_logs` rows they generated were removed from `lingoadapt_dev` afterward. Playwright and `@axe-core/playwright` were installed temporarily and fully uninstalled again.

### Known limitations / follow-ups

- No real external error-tracking service is wired up (no Sentry/Rollbar account exists for this project) - the structured logging + request-id correlation built this phase is the foundation such a service would plug into, deliberately stopping short of inventing credentials for one.
- No live dependency-vulnerability scan was run (no scanner configured in this environment) - `pip-audit`/`npm audit` (or a hosted equivalent) against the pinned versions in `pyproject.toml`/`package.json` would be a reasonable first step before a real launch.
- The backup strategy provides the mechanism (tested, working scripts) but not a schedule - there's no production host yet to put it on a cron/Task Scheduler job, and a managed Postgres provider would likely replace this with its own built-in backup feature entirely.
- Load testing was single-machine and local-Postgres only - it validates the app doesn't fall over under moderate concurrency, not what it can sustain against a real production database and network.
- Rate limits (10/min auth, 30/hour AI) are reasonable starting points, not tuned against real traffic - there is none yet to tune against.
- `docker-compose.yml`'s path remains untested in this environment specifically (Docker Desktop's daemon doesn't start here, noted since Phase 0) - Postgres and Redis were both verified natively instead.

## Phase 11 notes

### What was implemented

This phase is entirely a read layer over data every prior phase was already recording - no new learner-facing behavior, no new events to capture, just aggregating and surfacing what's already there for `phases.md`'s eight metrics (daily active learners, lesson completion, practice completion, retention, AI latency, AI error rate, most common mistakes, weakest skills, improvement over time).

**AI call instrumentation** (`app/models/analytics.py`, `app/ai/metering.py`, `app/repositories/analytics_repository.py`): AI latency and error rate didn't exist as queryable data before this phase - `GroqAIProvider` computed `latency_ms` per call and logged it via Python's `logging` module, but nothing was configured to collect those logs anywhere durable, and nothing persisted success/failure to the database. A new `ai_call_logs` table (`AiCallLog`: operation, provider, model, latency_ms, success, error_type, user_id, created_at) and a `MeteredAIProvider` wrapper class close that gap. `MeteredAIProvider` implements the same `AIProvider` interface as `GroqAIProvider`/`FakeAIProvider` and wraps *any* provider instance, timing every `chat()`/`transcribe()`/`synthesize_speech()` call and recording success or failure (via `AIProviderError` subtype, since `AITimeoutError`/`AIRequestError` are both real degraded states worth tracking) - without touching a single line of `conversation_ai.py`, `evaluation_service.py`, or `speech_service.py`, which stay exactly as provider-agnostic and independently testable as before. A new `get_metered_ai_provider` FastAPI dependency (`app/api/deps.py`) wraps `get_ai_provider()`'s singleton with a request-scoped `MeteredAIProvider` carrying the authenticated user's id and the live DB session, swapped in wherever `exercises.py`/`practice.py`/`tutor.py` previously depended on `get_ai_provider` directly. Because tests override `get_ai_provider` with `FakeAIProvider` at the dependency-injection layer (not by monkeypatching), every existing AI-endpoint test automatically started exercising `MeteredAIProvider` too, with zero test changes required - confirmed by the full suite passing unmodified.

The metrics-write itself is deliberately isolated from the request's main transaction: every current AI call site invokes the provider *before* writing any learner state (the same "AI failure must not corrupt learning state" invariant `conversation_service.send_message` already documents), so at the point a call completes or fails, nothing else is pending on that DB session - `MeteredAIProvider._record()` commits immediately rather than just flushing, and wraps the whole write in a try/except that swallows and logs any failure rather than ever letting a metrics-write problem break the actual AI feature a learner is waiting on.

**Analytics repository and service** (`app/repositories/analytics_repository.py`, `app/services/analytics_service.py`): every metric reads from data that already existed - `LearningEvent` for daily active users, retention, and the weekly-improvement trend; `LessonAttempt`/`PracticeSession` for completion rates; `DetectedError` for most-common-mistakes; `SkillMastery` for weakest skills; the new `AiCallLog` for latency/error rate. Daily/weekly bucketing reuses the exact UTC-explicit-bounds pattern `gamification_repository._utc_day_bounds` established in Phase 9 after a real timezone bug there (`func.date()` truncating in the Postgres session's local timezone rather than UTC) - a fresh `_utc_day_bounds` helper with the same reasoning lives in `analytics_repository.py` rather than importing the Phase 9 one, since that one is module-private by convention. Retention is defined as a standard N-day-return cohort ("of users active on day D-n, how many were also active on day D") rather than first-ever-activity cohorting, since this schema has no per-user "first seen" bookkeeping to build the latter from.

**Admin dashboard** (`GET /admin/analytics/overview?days=30`, `frontend/src/app/admin/analytics/page.tsx`): a single endpoint bundles all eight metrics rather than one round-trip per chart, since the whole dashboard is one page. The frontend renders it with plain CSS bar/sparkline visualizations (no charting library added - the project has none today, and eight simple aggregate views don't justify introducing one) built from a small `Card`/`Bar`/`Section` set of local components. Linked from the course-editor page (`/admin` → "Analytics →").

### Verification performed

- Backend: `pytest -q` - 234 passed (18 new: `test_ai_metering.py` covers `MeteredAIProvider`'s success and failure paths including that a timeout still propagates to the caller after being logged; `test_analytics_repository.py` seeds real rows and checks each aggregation function's arithmetic directly, including the "untouched skill" exclusion from weakest-skills and the empty-cohort retention edge case; `test_admin_analytics_api.py` covers access control and that the endpoint's response reflects seeded `AiCallLog` rows). `ruff check .` and `mypy app` clean (94 source files).
- Migration `45e2477bc564_add_ai_call_logs_table` generated via `alembic revision --autogenerate` (required first registering the new model in `app/models/__init__.py`, which `alembic/env.py` imports to populate `Base.metadata` - autogenerate silently produced an empty migration the first time, which was caught before applying it rather than assumed correct) and applied to the live dev database.
- **Verified against real, live-generated data end-to-end**, not just seeded rows: signed up a real learner, drove them through completing an admin-authored lesson via the actual `/exercises/{id}/answer` API (2 of 4 exercises answered correctly), then started a real AI tutor conversation and sent a message with a genuine grammar mistake ("I go to restaurant yesterday and I eat pizza") to a live Groq call. Promoted a second user to admin via `promote_admin.py` and fetched `/admin/analytics/overview` as them: daily active users showed exactly 1 for that day and 0 for prior days; lesson completion showed 100% (1/1 lesson attempts completed); AI stats showed 1 real CHAT call with 0% error rate and **1552ms average latency - the actual Groq response time**, not a placeholder; top mistakes showed the AI's real correction classified as `OTHER`; weakest skills showed "General Grammar" at 0/100 mastery (the fresh conversation-correction skill) below "Greetings" at 24/100 (the lesson just attempted) - the ordering and values matched exactly what the underlying learner actions should produce.
- **Browser verification** (Playwright, installed temporarily then removed again): logged in as the promoted admin and loaded `/admin/analytics`, confirming the dashboard renders all seven sections with the same real numbers as the direct API check, with no application console errors (the only console entries were pre-existing benign 401s from the app's silent-refresh-on-load check finding no session yet - unrelated to this phase, reproducible on any fresh login). One real friction point surfaced and worked around during this pass, not an application bug: Next.js 16's dev server blocks cross-origin requests to `/_next/static/*` by default, so driving the dev server via `127.0.0.1` (rather than `localhost`, which it treats as same-origin) silently broke client-side hydration and made a form submit as a plain unhandled GET - switching the verification script to `localhost` resolved it immediately.
- All verification data (2 users, their lesson/conversation/mastery/detected-error rows via cascade delete, and the one `ai_call_logs` row left behind by `ON DELETE SET NULL` after the users were removed) was deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- AI latency/error-rate instrumentation only covers the four call sites that route through `AIProvider` (`chat`/`transcribe`/`synthesize_speech`) - it's a wrapper around that interface, not a global HTTP-level trace, so it can't see non-AI request latency. Full request-latency/APM-style monitoring is explicitly Phase 12 scope ("error monitoring, logging" under Production Hardening).
- Retention is a simple day-N-return cohort, not full cohort-retention-curve analysis (e.g. week-over-week retention triangles) - sufficient to answer "are people coming back," not to power a growth-team-style retention deep dive.
- The dashboard has no date-range picker in the UI (the API accepts `days`, 1-90, but the page hardcodes 30) and no CSV/export path - reasonable for "admin can understand product and learning performance" at this stage, not for ongoing BI work.
- Weekly-improvement and daily-active-user queries are one-query-per-bucket (day or week) rather than a single grouped query, deliberately mirroring the UTC-bounds pattern that already caught a real timezone bug in Phase 9 rather than introducing a new date-bucketing mechanism. Fine at current data volume; worth revisiting with a single `date_trunc(..., 'UTC')`-based query if the admin dashboard's data volume or query-count budget becomes a real concern.
- No caching on the analytics endpoint - every dashboard load recomputes everything from raw event tables. Acceptable for an admin-only, low-traffic page; would need caching before exposing anything analytics-derived to learners at scale.

## Phase 10 notes

### What was implemented

**Admin authentication** (`User.is_admin`, `app/api/deps.py:get_current_admin_user`): a boolean flag with no self-serve path to `True` - rules.md §1.12 treats authorization as server-owned, deterministic state, so there's deliberately no "become an admin" API endpoint. Granted only via `python -m app.promote_admin <email>`, an operator-run script against the database directly (same trust boundary as running a migration), mirroring `app/seed.py`'s existing pattern of a runnable module rather than an HTTP surface. Every admin route is gated by a single shared FastAPI dependency (`dependencies=[Depends(get_current_admin_user)]` on the whole router), not repeated per-endpoint.

**Full course-authoring CRUD** (`app/repositories/course_repository.py`, `app/services/admin_content_service.py`, `app/api/v1/admin.py`): languages, courses, units, lessons, skills, and exercises (including their options), all under `/api/v1/admin/*`. New courses default to `is_published=False` (draft) regardless of the `Course` model's own default - admin-created content stays invisible to learners until deliberately published, distinct from `app/seed.py`'s courses which are still published immediately since they're trusted first-party content, not draft authoring. Exercise options are replaced wholesale on every save (`replace_exercise_options`) rather than diffed, since an exercise's option list is small and always edited as a complete set in the admin UI - simpler and less error-prone than add/update/remove reconciliation.

**Content validation before publish** (`app/services/content_validation.py`), per rules.md §7 ("Generated exercises must be validated before publication") - the rule is about what gets published, not who authored it, so the same validator applies to admin-authored content. Checks structural gradeability per exercise type (MULTIPLE_CHOICE needs exactly one correct option, WORD_ORDER's `correct_position` values must form a complete 0..n-1 sequence, MATCHING's left/right options must pair 1:1 by `match_key`, SHORT_ANSWER needs both a model answer and rubric, SPEAKING/LISTENING need their hidden answer keys, etc.) plus course-tree completeness (every unit has a lesson, every lesson has an exercise). `POST /admin/courses/{id}/publish` re-runs this and rejects with a 422 listing every problem if anything fails; a separate `GET /admin/courses/{id}/validate` lets the admin check before attempting to publish.

**Frontend**: `/admin` (course list with draft/published badges, new-course form with inline "add a language" disclosure), `/admin/courses/[courseId]` (skills, units/lessons tree with inline add, Validate/Publish/Unpublish), `/admin/lessons/[lessonId]` (exercise list plus a single adaptive creation form that reveals the right fields per exercise type - options with a correctness radio for MULTIPLE_CHOICE, a comma-separated word list for WORD_ORDER, left/right pair rows for MATCHING, model-answer/rubric for SHORT_ANSWER, and so on for all 8 types). An amber-accented "Admin" card appears on the dashboard only when `user.is_admin` is true.

### Two real bugs this phase caught

**Course deletion via raw SQL violated a foreign key that the real API doesn't.** Cleaning up test data with a direct `DELETE FROM courses ...` repeatedly hit `ForeignKeyViolation: ... still referenced from table "exercises"` - `exercises.skill_id` has no `ON DELETE CASCADE` (correctly so; deleting a skill shouldn't silently delete graded history), and Postgres doesn't guarantee that the `courses → units → lessons → exercises` cascade path finishes before the sibling `courses → skills` cascade path fires, so a raw cascading `DELETE` can try to remove a skill while an exercise still points at it. The *actual* `DELETE /admin/courses/{id}` endpoint doesn't have this problem - SQLAlchemy's ORM-level unit-of-work computes proper delete ordering across relationships (exercises before skills) regardless of the DB-level cascade graph, verified by calling the real endpoint on a full course tree (skills + exercises attached) and confirming a clean `204`. The bug was entirely in the ad-hoc verification cleanup scripts bypassing the ORM, not in the application - but it's a genuine trap for any future raw-SQL maintenance script touching this schema, so it's documented here rather than silently worked around.

**`/learn` only ever showed the first course, alphabetically.** A leftover simplification from Phase 1, when exactly one course could ever exist - `courses[0]` was hardcoded. This became a real bug the moment Phase 10 made a second course possible: after authoring and publishing a whole new course through the admin UI, a live browser walkthrough found it silently unreachable from the learner-facing side, because "English Foundations" sorted first and `/learn` never looked past it. Fixed by adding a course picker (skipped automatically when there's only one course, preserving the exact prior UX for the common case) - re-verified live by publishing a second course and confirming a learner could pick it and complete a lesson inside it.

### Verification performed

- Backend: `pytest -q` - 216 passed (29 new: `test_content_validation.py` - all 8 exercise types' pass/fail conditions plus course-tree completeness, using transient never-persisted model instances since the validator only reads attributes; `test_admin_api.py` - access control (403 for non-admin, 401 for unauthenticated), duplicate language/skill code rejection, the full draft → author → validate → publish → learner-visible lifecycle, multiple-choice option round-tripping, exercise option replacement on update, and cascading delete order). `ruff check .` and `mypy app` clean (87 source files).
- **Verified against the real dev database end-to-end, twice over**: first a scripted `httpx` walkthrough (promote a real user via the real `promote_admin` script, create a language/course/unit/lesson/skill, confirm validation correctly blocks an empty lesson, add a MULTIPLE_CHOICE exercise, confirm validation now passes, publish, confirm the course appears in the public `/courses` list, then fetch the lesson and submit the correct answer as a real learner and confirm real XP was awarded) - then repeated for WORD_ORDER, MATCHING, and LISTENING to confirm each type's option/answer shape round-trips correctly through the admin API, including confirming LISTENING's hidden `text_to_speak` never leaks into the learner-facing payload (same boundary Phase 8 established for SHORT_ANSWER/LISTENING).
- **Browser verification** (Playwright, installed temporarily then removed again): signed up, promoted to admin via the real script, reloaded to pick up the fresh `is_admin` flag, and drove the *entire* authoring flow through the real UI - added a language, created a draft course, added a skill/unit/lesson, created a MULTIPLE_CHOICE exercise through the adaptive form, validated, published - then switched to the learner-facing `/learn` page (which required the course-picker fix above to even reach the new content) and completed the authored exercise for real, seeing the same "Correct!" feedback UI as hand-seeded content.
- Frontend: `npx vitest run` - 48 passed (9 new: `admin-api.test.ts` covering every admin client function's request shape and response parsing). `npx eslint .` and `npx tsc --noEmit` clean, `npm run build` succeeds (18 routes now - `/admin`, `/admin/courses/[courseId]`, `/admin/lessons/[lessonId]` added).
- All test/demo courses, languages, and users created during verification (including several duplicate courses from repeated script runs, cleaned up via the real admin API rather than raw SQL once the FK-ordering issue above was understood) were removed from `lingoadapt_dev` afterward, leaving only the original seeded `English Foundations` course.

### Known limitations / follow-ups

- No reordering UI for units/lessons/exercises within their parent - `position` can be set explicitly on create, but there's no drag-and-drop or explicit "move" endpoint yet. A real content team would want this quickly; deferred since the exit criteria only requires *creating* a course without touching source code, not full authoring ergonomics.
- No image/audio upload for course content - exercises can reference text and (via Phase 8's existing TTS pipeline) synthesized speech, but there's no admin-side asset upload flow, consistent with this stack having no object storage yet (documented in Phase 8's notes too).
- No bulk import (e.g. CSV/JSON course upload) - every unit, lesson, and exercise is created one at a time through the API/UI. Reasonable for the MVP's content scale; a real content pipeline would likely want a bulk path eventually.
- No audit log of admin actions (`project_requirement_document.md` §"Audit sensitive admin operations" is noted there but not implemented) - every write is deterministic and attributable via normal request logging, but there's no dedicated admin-activity table yet.
- Skills have no delete endpoint, deliberately - once a skill has any learner mastery/learning-event history attached, deleting it would either cascade-destroy that history or orphan it. Renaming (`PATCH /admin/skills/{id}`) is supported; removal is not, matching this project's general stance of never discarding persisted learner state.

## Phase 9 notes

### What was implemented

**Weekly leagues** (`app/services/league_service.py`): five original tiers (Spark → Ember → Blaze → Aurora → Zenith - not Duolingo's bronze/silver/gold naming, per `design.md`'s "do not make it look like a direct clone of Duolingo"). This stack has no background-job runner, so promotion/demotion is computed *lazily*: reading a user's league checks whether their `week_start` has fallen behind the current calendar week and, if so, ranks their just-finished week against whichever tier-mates still share that same (now-stale) `week_start`) - a cohort that forms naturally from shared activity cadence rather than a scheduler-assigned fixed-size pool. Top ~30% promote, bottom ~30% demote, and cohorts smaller than 3 never move (not enough people to rank fairly). No cron job needed for this to stay correct.

**Daily quests** (`app/services/quest_service.py`): three templates - earn 30 XP, complete a lesson, finish a practice session - every one tied to a real learning action already tracked elsewhere in the app, per `rules.md` §8.2/§8.3 ("do not reward meaningless button clicking"). Progress is computed *live* from existing data (today's XP transactions, completed lessons, completed practice sessions) on every read rather than mirrored into a separately-mutated counter, the same style `xp_today` already used before this phase.

**Virtual currency** (gems): `app/services/currency_service.py`, a thin wrapper mirroring `XPTransaction`'s idempotency pattern - a `(source_id, reason)` pair can only ever be awarded once, enforced at the DB level. Gems come from quest completions and achievement unlocks only, never from raw activity - "rewards" in this phase means connecting existing gamification signals to a spendable balance, not building a redemption shop (out of scope, noted below).

**Friend system** (`app/models/social.py`, `app/services/friend_service.py`): a single directed `friendships` row per pair (requester → addressee) that becomes symmetric once accepted - the service checks both directions before creating a new request so a pair can never end up with duplicate/conflicting rows. Friends can be added by email (there's no username system yet), and a friends-scoped leaderboard ranks the learner against their accepted friends by this calendar week's XP - simpler than league leaderboards since there's no promotion state to track, just a live query.

**Achievement catalog extended**: three new codes tied to the new systems - `QUEST_MASTER` (10 quests completed), `FIRST_FRIEND` (first friend added), `RISING_STAR` (promoted a league tier). `gamification_service._evaluate_achievements` was refactored to take an already-built context object instead of building one internally, so quest completion, friend acceptance, and league promotion can all trigger evaluation without being lesson-completion-shaped. Achievement unlocks now also award gems (20 each), closing the loop between the achievement and currency systems.

**`ProgressOut` extended** with `gem_balance` and `league_tier`, so the existing `/me/progress` dashboard call picks up both without a separate round-trip. New endpoints: `GET /me/quests`, `GET /leaderboard` (league), `GET /leaderboard/friends`, `GET/POST /friends`, `POST /friends/requests`, `POST /friends/requests/{id}/accept`, `DELETE /friends/{id}`.

**Frontend**: `GemBadge` and `QuestCard` components (mirroring the existing `StreakBadge`/`AchievementCard` style), a `/leaderboard` page (league/friends tabs), a `/friends` page (add by email, incoming/outgoing requests, friend list), and a new "Compete" card on the dashboard linking to both plus a "Daily quests" card showing live progress bars.

### Two real bugs this phase caught

**A genuine pre-existing timezone bug, not something Phase 9 introduced but exposed by it.** `get_xp_earned_on` (added in Phase 2, powering the dashboard's "XP today" bar) compared `func.date(created_at) == day` in SQL. This dev machine's Postgres session timezone is `Asia/Calcutta` (UTC+5:30); `func.date()` truncates using that session timezone, while the `day` value being compared against came from Python's `datetime.now(UTC).date()`. Whenever the wall clock is between UTC midnight and IST midnight (a ~5.5-hour window, every single day), the two disagree about which calendar day it is, and the comparison silently returns wrong results. This was caught live: `tests/test_gamification.py::test_progress_endpoint_reflects_completed_lesson` failed with `xp_today == 0` instead of `50` purely because of *when* the test happened to run. Fixed by comparing against explicit UTC datetime range bounds (`created_at >= start AND < end`) instead of relying on the DB session's timezone GUC at all - applied to the pre-existing function plus the two new date-scoped quest-progress queries this phase added, which would have carried the identical bug forward.

**GET-triggered state mutation wasn't persisting.** League creation/rollover and quest generation/completion are deliberately triggered lazily by reads (`GET /me/progress`, `GET /me/quests`) rather than a scheduled job - but this codebase's repository functions only ever `flush()`, never `commit()`; every existing commit happens explicitly at the service layer on a clear write path (POST endpoints). Since `get_db()`'s session is closed without an explicit rollback OR commit at request end, an uncommitted flush is silently discarded when the connection returns to the pool. The first version of `league_service.get_or_create_league` and `quest_service.get_quest_progress` didn't account for this - caught before it reached a live test by re-reading the ordering rules established in earlier phases (Phase 7's message-ordering fix, Phase 8's idempotency-pre-check fix) and reasoning through what a GET-only session lifecycle actually persists. Fixed by committing explicitly at the end of both lazy-mutation entry points, verified live end-to-end (see below).

### Verification performed

- Backend: `pytest -q` - 187 passed (33 new: `test_league_service.py` - week-start Monday math, new users starting at Spark, no-op reads within the same week, a small cohort never moving tier, a real 5-person cohort's top member being promoted and a real 5-person cohort's bottom member being demoted from a non-starting tier, and leaderboard ranking; `test_quest_service.py` - idempotent quest generation, live progress reflecting real XP, first-completion awarding currency, re-reading an already-completed quest never double-awarding, progress capped at target, and the 10-quest achievement threshold; `test_friend_service.py` - request/accept/decline flows, self-friend and duplicate-request rejection, only-the-addressee-can-accept, third-party-cannot-remove, the FIRST_FRIEND achievement unlocking on acceptance, and friends-leaderboard scoping; `test_phase9_api.py` - the same flows end-to-end through the real HTTP API). `ruff check .` and `mypy app` clean (82 source files).
- **Verified against the real dev database end-to-end**, not just the test suite: completed a real lesson via the live API and confirmed all three quests progressed correctly (two completing immediately, XP-quest capped exactly at its target), gem balance landed at exactly 65 (10 + 15 quest rewards + 20 + 20 achievement rewards - hand-verified the arithmetic against the actual response), and both `FIRST_LESSON`/`PERFECT_LESSON` achievements unlocked. Separately verified the achievement catalog needed a real `python -m app.seed` re-run after adding the three new codes - the first live friend-acceptance test correctly found *no* `FIRST_FRIEND` award because the achievement row didn't exist in the dev DB yet, re-seeded, and a fresh pair of users then correctly both received it with gems. Verified the friends leaderboard correctly excludes a non-friend third user and ranks by real weekly XP.
- **Browser verification** (Playwright, installed temporarily then removed again): signed up, completed a real lesson, confirmed the dashboard's Daily Quests card, gem badge, league "Compete" card, and updated achievement grid (locked vs. unlocked states) all rendered correctly with real data; visited `/leaderboard` and confirmed both the League and Friends tabs render correctly; drove the *entire* friend-request flow through two real browser sessions (not just the API) - user A adding user B by email on the real `/friends` page, user B seeing the real incoming request and clicking the real Accept button, and confirming B's friends list then showed A.
- Frontend: `npx vitest run` - 39 passed (8 new: `gamification-api.test.ts`, `social-api.test.ts` covering every new client function's request shape and response parsing). `npx eslint .` and `npx tsc --noEmit` clean, `npm run build` succeeds (16 routes now - `/leaderboard` and `/friends` added, both static).
- Test users and demo data created during all verification passes were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- League cohorts form organically from shared `week_start` rather than fixed-size matchmaking pools (e.g. Duolingo's groups of ~30) - simpler and fully deterministic without a scheduler, but cohort size varies with how many tier-mates are active in the same window, and very small cohorts (below 3) never move tier at all.
- No redemption/shop system for gems - currency is earned but not yet spendable on anything. `project_requirement_document.md` §9 lists "virtual currency" as a requirement without specifying a shop, so this phase closed the earn-side loop and left spending for a later phase to scope deliberately rather than bolting on an under-specified shop mechanic.
- Friends are added by exact email match - there's no username/handle system or friend search/discovery yet, matching this project's auth model (email-only, no profile/display-name concept established in any earlier phase).
- No hearts/lives system, despite `project_requirement_document.md` §9 listing it as "if enabled" - deliberately left disabled since neither `phases.md`'s Phase 9 feature list nor any other spec document specifies a hearts/lives design (regeneration rate, loss conditions, etc.), and rules.md §8.5 ("do not create manipulative pressure") argues against inventing one speculatively.
- League promotion/demotion and quest rollover are only evaluated when a user is actually active (lazy-on-read) - an inactive user's league state simply stays frozen at their last-seen week rather than silently decaying, which seems like the more defensible default but means a returning user's very first read after a long absence does a slightly larger one-time catch-up computation (still O(1) in cohort size, not O(weeks missed), since only the *immediately* stale week is evaluated before `week_start` jumps straight to the current week).

## Phase 8 notes

### What was implemented

**AI Gateway extension** (`app/ai/base.py`, `app/ai/groq_provider.py`): `AIProvider` gained two more I/O primitives alongside `chat()` - `transcribe()` (speech-to-text) and `synthesize_speech()` (text-to-speech) - matching `architecture.md` §2's "Provider abstraction supporting: LLM, Speech-to-text, Text-to-speech." `GroqAIProvider` implements both against real Groq endpoints: `whisper-large-v3-turbo` for transcription (multipart upload, `{"text": ...}` response), `canopylabs/orpheus-v1-english` for speech (JSON in, raw WAV bytes out). Orpheus has a real, documented 200-character input limit - long conversational replies are truncated at a word boundary before synthesis rather than failing outright.

**Deterministic pronunciation feedback** (`app/services/pronunciation.py`): `architecture.md` §2 lists pronunciation scoring as an "optional" AI capability, and no provider in this stack actually offers phoneme-level scoring. Rather than fabricate an AI opinion about pronunciation quality, this module gives the one thing genuinely derivable from a transcript - word-level diff between the expected phrase and what speech-to-text heard (`difflib.SequenceMatcher` over normalized word lists) - and surfaces which words matched/didn't as plain factual feedback. Critically, this is also what grades SPEAKING exercises: `rules.md` §2's "never let an LLM determine correctness" applies even though the *input channel* is AI-mediated (transcription) - correctness is a deterministic similarity-ratio comparison against `Exercise.correct_answer["answers"]`, the same family as FILL_BLANK/TRANSLATION's exact-match grading, just tolerant of minor STT noise via a 0.9 similarity threshold.

**Two new exercise types** (`ExerciseType.SPEAKING`, `ExerciseType.LISTENING`): SPEAKING shows a phrase to say aloud (`payload.phrase_to_say` - safe to expose, that's the exercise itself) and grades a submitted recording's transcript against accepted phrasings. LISTENING is dictation - the target text lives in `correct_answer.text_to_speak` (never `payload`, so it can't leak to the client the way SHORT_ANSWER's `model_answer` doesn't), synthesized on demand via a new `GET /exercises/{id}/audio` endpoint and graded with the exact same exact-match logic as FILL_BLANK. Required the same `ALTER TYPE ... ADD VALUE` + `autocommit_block()` migration treatment as Phase 6/7's enum additions.

**Audio submission endpoints**: `POST /exercises/{id}/answer-audio` and `POST /practice/{session_id}/answer-audio` (multipart upload) transcribe once at the API boundary, then delegate into the *exact same, unmodified* `lesson_service.submit_answer`/`practice_service.submit_practice_answer` a typed JSON answer would use - grading itself (`app/services/grading.py`) never touches audio. `POST /tutor/conversations/{id}/voice-messages` does the same for conversation turns, reusing all of Phase 7's correction/learning-event/mastery logic unchanged. A new `GET /tutor/conversations/{id}/messages/{message_id}/audio` synthesizes (and caches) any tutor reply's audio on demand, so both voice- and text-originated conversations get playback.

**No object storage** (`app/services/speech_service.py`): `architecture.md` §2 recommends object storage for audio in production; out of scope for local dev with no cloud credentials. Instead: synthesized audio (exercise/message playback) is cached in-memory per process, keyed by the immutable id that produced it, so repeat fetches never re-pay for a second AI call; submitted speech (STT input) is never persisted at all - only its transcript matters downstream, consistent with `memory.md` §4's "memory should remain useful and compact," not a raw-media log.

**Frontend**: `useAudioRecorder` hook (MediaRecorder-based, browser mic) shared by `SpeakingAnswer` (record → preview → submit, mirrors `ExerciseRenderer`'s existing exercise-type dispatch) and the tutor chat's voice composer (record → preview → send, alongside the existing text composer). `ListeningAudioPlayer` fetches and autoplays an exercise's audio. Tutor message bubbles gained a 🔊 play button that lazily fetches and plays that message's TTS audio. `apiRequest`/`apiRequestBlob` in `lib/api-client.ts` were extended to handle `FormData` bodies (skip the forced JSON content-type so the browser sets its own multipart boundary) and raw-blob responses.

### Two real bugs this phase caught

**A live-API blocker, not a bug**: the first real Groq TTS call returned `400 model_terms_required` - `canopylabs/orpheus-v1-english` requires one-time terms acceptance by the account/org admin before any API call succeeds, discovered only by actually calling the real endpoint (speech-to-text worked immediately; text-to-speech didn't). This isn't something code can work around - flagged to the user, who accepted the terms in the Groq console, and the exact same call succeeded immediately afterward. Documented in `.env.example` as a real setup step for anyone standing this up fresh.

**Resubmitting a SPEAKING exercise wastefully re-transcribed audio.** `lesson_service.submit_answer` already has an idempotency check (never recompute a cached grade - the same protection Phase 6 added for SHORT_ANSWER's paid AI grading calls), but for audio answers that check happens *after* transcription, which is itself a real, billed AI call happening one layer up at the API boundary. Live-verified: resubmitting the same exercise with completely different audio returned the *original* cached grading result but the endpoint's own `transcript` field showed the *new* audio's real transcript - proof a wasted STT call had actually happened and been silently discarded. Fixed by adding a read-only idempotency pre-check (`lesson_service.get_existing_answer`, `practice_service.get_existing_answer`) that runs *before* transcription and reuses the original stored transcript on a cache hit - re-verified live against Groq (same request, different audio, now returns the *original* transcript both places, confirming zero second STT call). A smaller version of the same class of bug (expensive work before a cheap ownership check) was caught and fixed in the voice-conversation endpoint too, before it ever reached a live-API test.

### Verification performed

- Backend: `pytest -q` - 154 passed (21 new: `test_pronunciation.py` covering the similarity ratio, threshold, and diff-feedback functions in isolation; `test_speaking_listening.py` covering SPEAKING/LISTENING payload leak-safety, correct/incorrect speaking grading with feedback text, practice-session integration, the resubmission-doesn't-re-transcribe regression, oversized-upload 413s, AI-timeout-leaves-no-trace, and the listening audio endpoint's caching and type-gating; `test_voice_conversation.py` covering voice message transcription, silent-recording 400s, AI-failure-leaves-no-trace, oversized uploads, message-audio caching, 404s for non-tutor/nonexistent messages, and the ownership-before-transcription ordering fix). `ruff check .` and `mypy app` clean (73 source files).
- **Verified against the real Groq API end-to-end, both directions**: synthesized a LISTENING exercise's hidden text via the real `/exercises/{id}/audio` endpoint, then independently transcribed that exact audio back via real Whisper and got back the exact original text - a full TTS→STT round-trip proving content correctness, not just structural plausibility. Separately synthesized a SPEAKING exercise's target phrase, submitted it as a real audio file through the real `answer-audio` endpoint, and got back `is_correct: true` with `"Great pronunciation - every word matched!"` - then submitted an unrelated synthesized phrase as a resubmission and confirmed (post-fix) the cached original transcript was correctly returned both places, with zero additional Groq API calls.
- **Browser verification** (Playwright with `--use-fake-device-for-media-stream`/`--use-file-for-fake-audio-capture` feeding a real synthesized WAV as the fake microphone, installed temporarily then removed again): completed all four exercises of a real lesson including a genuine recorded SPEAKING answer, confirmed the rendered feedback showed the real transcript and "Correct!"/pronunciation note; completed a LISTENING exercise with the real audio player and dictation input; started a real tutor conversation, recorded and sent a real voice message, confirmed the AI's reply and a grammar correction rendered correctly, and confirmed clicking the reply's 🔊 button played real synthesized audio back.
- Frontend: `npx vitest run` - 31 passed (5 new: `sendVoiceMessage`/`getMessageAudio` in `tutor-api.test.ts`, `submitAnswerAudio`/`getExerciseAudio` in `course-api.test.ts`, `submitPracticeAnswerAudio` in `practice-api.test.ts`, all asserting correct multipart/blob handling). `npx eslint .` and `npx tsc --noEmit` clean, `npm run build` succeeds (same 12 routes as Phase 7 - voice reuses `/learn`, `/practice`, and `/tutor/[conversationId]`, no new pages needed).
- Test users and demo data created during both real-API and browser verification were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- No object storage for audio (see above) - fine for this single-process local-dev scale (in-memory cache), but a real deployment needs a persistent cache/CDN in front of object storage per `architecture.md` §2, especially once there's more than one backend process (the in-memory cache wouldn't be shared).
- Pronunciation feedback is word-level text diff only, not real phoneme/accent scoring - honestly scoped to what's actually derivable without a dedicated pronunciation-analysis provider, per this phase's "real bugs" note above about not fabricating AI capability that doesn't exist.
- Learner-submitted speech audio is never persisted, only its transcript - matches `memory.md`'s "memory should remain useful and compact," but means there's no way to go back and re-listen to a past spoken answer, unlike TTS-generated audio which is cheaply re-synthesizable from cached text.
- The 200-character Orpheus input limit means a long tutor reply's audio is truncated (at a word boundary) rather than synthesized in full - fine for typical short conversational turns, but a very long reply's audio would end mid-thought.
- No leaderboards/currency/streak-freeze audio cues or other voice-adjacent gamification hooks - `phases.md` assigns "Advanced Gamification" to Phase 9 explicitly, so this is deferred on purpose.

## Phase 7 notes

### What was implemented

**Data model**: two new tables, `conversations` (user, scenario, status, deterministic `summary`, `started_at`/`ended_at`) and `conversation_messages` (role `LEARNER`/`TUTOR`, content, ordered by `created_at`). `learning_events.exercise_id` and `detected_errors.exercise_id` became nullable, each gaining a sibling `conversation_message_id` FK and a `CheckConstraint` enforcing exactly one of the two is set (`(exercise_id IS NOT NULL)::int + (conversation_message_id IS NOT NULL)::int = 1`) - a single append-only learning-events log and a single detected-errors log now serve both exercise answers and conversation mistakes, rather than forking into parallel tables. `LearningEventType` gained `CONVERSATION_CORRECTION`, requiring the same `op.get_context().autocommit_block()` migration treatment Phase 6's `SHORT_ANSWER` enum addition needed (Postgres can't `ALTER TYPE ... ADD VALUE` inside a transaction) - verified again by querying `pg_enum` after applying.

**Grammar skill catalog** (`app/seed.py`'s `seed_grammar_skills()`): seven skills - `PAST_TENSE`, `PREPOSITIONS`, `ARTICLES`, `SUBJECT_VERB_AGREEMENT`, `PLURALS`, `WORD_CHOICE`, `GENERAL` - tied to the same "English Foundations" course, idempotent like every other seed step. This is the vocabulary conversation corrections resolve against: the AI's free-text `skill` field gets keyword-normalized (same pattern as Phase 6's error `type`/`severity`) to one of these seven, then mapped to a real `skill_id` so a conversation mistake feeds the exact same `skill_mastery` row an exercise answer would.

**Learner Context Builder** (`app/services/learner_context.py`), matching `memory.md` §5's object shape exactly: `target_language`, `estimated_level` (a new deterministic `estimate_level()` pure function banding average mastery across six CEFR levels A1-C2 - arbitrary but documented, since there's no ground-truth mapping and `rules.md` forbids letting an LLM decide this), `current_topic` (the scenario), `weak_skills`/`strong_skills` (skills with ≥3 attempts, below/above a 50/80 mastery threshold), and `recent_errors` (last 5 `detected_errors` descriptions). Deliberately compact per `memory.md`: "Do not send the entire database history to the model."

**Conversation AI** (`app/services/conversation_ai.py`, `app/schemas/conversation.py`): the system prompt encodes `rules.md` §6's 8 conversation rules directly (maintain context, speak at learner's level, encourage production, don't take over, correct without interrupting every sentence, distinguish real mistakes from natural variation, adapt vocabulary, stay in character) plus a structured JSON contract (`reply` + `corrections[]`), mirroring Phase 6's two-tier validation: `reply`/`original`/`corrected`/`explanation` are structurally strict, `skill` is keyword-normalized. Full message history is replayed as alternating `user`/`assistant` turns on every call so the model has real conversational memory, not just a single-turn context.

**Orchestration** (`app/services/conversation_service.py`, `app/api/v1/tutor.py`): `POST /tutor/conversations` (start), `GET /tutor/conversations` (history list), `GET /tutor/conversations/{id}` (detail with messages), `POST /tutor/conversations/{id}/messages` (send + get AI reply + corrections), `POST /tutor/conversations/{id}/end` (deterministic summary, no AI call - `models/conversation.py`'s docstring and `rules.md` §2.6 "avoid unnecessary AI calls" for something derivable locally, e.g. `"Restaurant conversation: 2 learner messages (4 total)."`). Each flagged correction triggers `evaluation_repository.record_detected_error` (same table Phase 6 uses) and `learner_model_service.record_conversation_mistake` (a new sibling to `record_answer_learning_event`, sharing a refactored-out `_apply_learning_event` helper) - so a conversation mistake updates `skill_mastery`/spaced-repetition scheduling exactly like a wrong exercise answer would.

**Frontend**: `/tutor` (scenario picker with all 7 example scenarios from `phases.md`, plus conversation history with status badges and deterministic summaries) and `/tutor/[conversationId]` (chat UI - right-aligned learner bubbles, left-aligned tutor bubbles, inline correction cards showing struck-through original → corrected + explanation, an "End conversation" action, Enter-to-send). `lib/tutor-api.ts` + `types/conversation.ts` follow the same shape as every other API client in the app. The dashboard's old "AI tutor arrives in a later phase" placeholder card now links to `/tutor`.

### A real bug this caught

**The AI re-flagged already-corrected mistakes on every subsequent turn.** Sending a message with a genuine mistake, then a clean follow-up message, still produced the *same* correction a second time - because the full conversation history was replayed on every call and the model kept re-scanning old turns for mistakes rather than only the latest one. Caught via real-Groq browser verification (not the fake-provider test suite, which doesn't have this failure mode since it returns whatever's queued): `attempt_count` on the mastery row incremented on the clean second turn too, meaning a learner would get silently, repeatedly penalized for a mistake they'd already fixed. Fixed by adding an explicit instruction to the system prompt: "only include a correction for a mistake in the learner's LATEST message... never re-report a mistake from an earlier message." Re-verified live against Groq afterward - a second clean turn now correctly returns zero corrections and `attempt_count` stays flat.

A second, smaller ordering bug was caught by the *fake*-provider test suite before it ever reached Groq: the learner's message was originally persisted (`db.flush()`) *before* calling the AI, so a failed AI call (timeout/malformed response) still left the message visible within the same request's DB session even though never committed - violating the same "AI failure must not corrupt state" invariant Phase 6 established. Fixed by reordering `conversation_service.send_message` to only write messages after the AI call succeeds (matching `ai_grading.py`'s existing pattern), verified by a test asserting zero `ConversationMessage` rows exist after a simulated timeout.

### Verification performed

- Backend: `pytest -q` - 125 passed (20 new: `test_learner_context.py` covering all six CEFR band boundaries; `test_conversation_ai.py` - successful parsing, skill keyword-normalization including the unrecognized-input fallback to `GENERAL`, malformed JSON / missing/empty `reply` all raising `AIResponseValidationError`, timeout and request-error propagation, against a `FakeAIProvider` extended with `queue_conversation_turn()`; `test_tutor.py` - conversation creation, message send/reply/corrections, learning-event + mastery updates from a correction, multi-turn history ordering and that later calls actually include earlier turns in the AI prompt, ownership checks (403/404), ending a conversation (deterministic summary, sending to an ended conversation returns 409), and the same AI-failure-writes-nothing / not-configured / malformed-response 503 coverage Phase 6 established). `ruff check .` and `mypy app` clean (71 source files).
- **Verified against the real Groq API**, not just the fake provider: a live multi-turn restaurant conversation with a deliberately flawed opening message ("I go to this restaurant yesterday and I want a table for two peoples please") correctly returned two corrections (`PAST_TENSE`: go→went, `PLURALS`: peoples→people) with accurate, well-formed explanations, both persisted as `DetectedError` rows and reflected in `skill_mastery` via `/me/errors` and `/me/mastery`. This run is what surfaced the re-flagging bug described above; a second live conversation after the prompt fix confirmed zero duplicate corrections on a clean follow-up turn, and ending the conversation produced the expected deterministic summary without any AI call.
- **Browser verification** (Playwright, installed temporarily then removed again): signed up, navigated dashboard → `/tutor` → started a Restaurant conversation, sent a message with real mistakes, confirmed the live Groq-backed reply and correction cards rendered correctly in the chat UI, ended the conversation, and confirmed the history list showed the correct scenario, "Ended" badge, and deterministic summary text.
- Frontend: `npx vitest run` - 26 passed (5 new: `tutor-api.test.ts` covering all five client functions). `npx eslint .` and `npx tsc --noEmit` clean, `npm run build` succeeds (13 routes now - `/tutor` static, `/tutor/[conversationId]` dynamic).
- Test users created during both real-API and browser verification were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- Conversation history loaded via `GET /tutor/conversations/{id}` doesn't include past corrections per message - `ConversationMessageOut` only carries role/content/timestamp. Corrections are shown live when a message is first sent (kept in frontend state) but disappear on reload. Fine for a single active session; would need a small schema/endpoint addition to persist and replay them if conversation review becomes a product requirement.
- `estimate_level()`'s CEFR banding is a documented but arbitrary linear split of the 0-100 mastery scale - there's no real CEFR-aligned assessment behind it. Reasonable for calibrating prompt tone, not something to expose as an official level claim to the learner.
- No limit on conversation length or a hard per-user concurrent-conversation cap - a learner can start unboundedly many conversations. Matches Phase 6's stance that AI cost controls are explicitly deferred to Phase 12 (Production Hardening).
- Corrections always get `DetectedErrorSeverity.MEDIUM` - unlike Phase 6's free-response evaluation, the AI isn't asked for a severity in the conversation schema (there wasn't a clear signal to base one on turn-by-turn), so this is a fixed default rather than a per-correction judgment.

## Phase 6 notes

### What was implemented

**AI Gateway** (`app/ai/`), matching `architecture.md` §10's shape: an `AIProvider` ABC with a single `chat()` primitive (the actual I/O boundary — timeouts, one retry on transient 5xx/timeout, latency + token-usage logging), and `GroqAIProvider` as the concrete implementation. Higher-level capabilities (`EvaluationService` today; `ConversationService`/`ExerciseGenerationService` in later phases) are built on top of `chat()` in `app/services/`, not baked into the provider — exactly the split the architecture doc describes ("Possible services" listed separately from `AIProvider` itself). Nothing outside `app/ai/` imports a provider SDK directly.

**New exercise type**: `SHORT_ANSWER` — free-form written answers, graded by AI instead of exact-match. Required a genuine Postgres migration gotcha: `ALTER TYPE ... ADD VALUE` cannot run inside the same transaction Alembic normally wraps a migration in, so that statement runs in its own `op.get_context().autocommit_block()`, verified by actually querying `pg_enum` afterward rather than just trusting it worked.

**Structured, validated AI output** (`app/schemas/evaluation.py`), matching `architecture.md` §11's exact shape (`is_correct`, `score`, `errors[]`, `explanation`, `corrected_answer`). Two-tier validation: the outer structure is strict (wrong types reject outright - `is_correct`/`score`/`explanation`/`corrected_answer` are meaningless if malformed), but each error's `type`/`severity` fields are keyword-normalized rather than strict-enum-matched, because live testing against Groq showed the model reliably returns lowercase/synonym values ("major" instead of "HIGH") despite being told the exact vocabulary — rejecting the whole response over casing would make a working feature fail unpredictably for cosmetic reasons.

**`detected_errors` table**: AI-classified errors from free-form evaluation, persisted per exercise answer and readable via `GET /me/errors`. This is the `detected_errors` table from the original task brief's database list, deliberately not built in Phase 4 - it only makes sense once there's AI-driven classification content to store, which this phase is what provides.

**Where AI grading plugs into the existing pipeline**: `app/services/ai_grading.py` bridges `evaluate_free_response`'s result into the same `(is_correct, correct_answer, explanation)` shape `app/services/grading.py` produces for the five deterministic types, so `lesson_service`/`practice_service` dispatch on `exercise.type` without needing separate code paths downstream - a correctly-evaluated SHORT_ANSWER answer flows through the exact same learning-event/mastery/XP/streak/achievement machinery a multiple-choice answer does. `is_correct` requires *both* the AI's own flag *and* `score >= 0.6` (rules.md: never trust AI output without validation - a numeric floor guards against a borderline `is_correct: true` paired with a contradictory low score).

**Async conversion**: `lesson_service.submit_answer` and `practice_service.submit_practice_answer` (and their routes) became `async def`, since AI grading is a real network call. Deterministic-type answers still resolve synchronously in effect - only the SHORT_ANSWER branch actually awaits anything.

**Failure handling**: global FastAPI exception handlers (registered once in `main.py`, not repeated per-route) turn `AIProviderNotConfiguredError` and any `AIProviderError` into a clean `503`, never a `500`. Both are raised *before* any database write in the grading path, so a failed AI call - timeout, malformed response, provider outage - leaves zero trace: no exercise attempt, no learning event, no mastery change, and the lesson/practice attempt stays `IN_PROGRESS` and retryable (verified directly in tests, not just asserted).

**Seed content**: one real SHORT_ANSWER exercise added to the existing "Introducing Yourself" lesson via a new idempotent `seed_short_answer_exercise()` step - added separately from `seed_english_foundations()` because that function's course-level "does it exist yet" check wouldn't retroactively add a new exercise to an already-seeded course.

### A real design gap this phase surfaced and fixed

**Resubmitting an exercise used to recompute its grade instead of storing it.** Fine when grading is free and deterministic (Phases 2-5); wrong the moment grading became a paid, non-deterministic AI call - re-submitting the same answer would silently re-charge and could return a *different* result the second time. Fixed by adding `correct_answer`/`explanation` columns to `exercise_attempts` and `practice_questions` and reading them back on resubmit instead of ever re-grading. This simplified the deterministic-type path too (one less function call on resubmit) and is verified directly: a test asserts a resubmitted SHORT_ANSWER exercise results in exactly one call reaching the fake AI provider, not two.

### Verification performed

- Backend: `pytest -q` — 105 passed (16 new: 7 pure `evaluation_service` tests against a `FakeAIProvider` — successful parsing, keyword-normalization of odd-cased error fields, malformed JSON / missing-field / out-of-range-score all raising `AIResponseValidationError`, timeout and request-error propagation — plus 9 integration tests covering the full SHORT_ANSWER flow: no leaked model-answer/rubric in the public exercise payload, correct/incorrect grading updating mastery identically to deterministic types, `DetectedError` persistence and retrieval via `/me/errors`, the `is_correct AND score>=0.6` floor, resubmission *not* re-invoking AI, a timed-out AI call leaving zero state behind, an unconfigured provider returning `503`, a malformed AI response returning `503` and writing nothing, and SHORT_ANSWER working inside practice sessions too, not just lessons). `ruff check .` and `mypy app` clean.
- **This phase was verified against the real Groq API**, not just the fake provider - `AI_API_KEY` was supplied directly for this session, stored only in the gitignored `backend/.env`, never committed or written anywhere else. A real `curl` walkthrough completing "Introducing Yourself" with a deliberately flawed short answer ("My name Ridhvan and I from India.") got back a real, well-formed evaluation identifying the missing "is"/"am", a sensible corrected sentence, and an encouraging explanation - correctly wired into `lesson_completed`, `xp_earned: 30` (3 of 4 correct), and a `FIRST_LESSON` achievement unlock, with both `DetectedError` rows retrievable via `/me/errors` afterward.
- **Browser verification** (Playwright, installed temporarily then removed again) against the same real Groq-backed server: signed up, completed three deterministic exercises, reached the real seeded SHORT_ANSWER exercise, submitted the same flawed sentence, and confirmed the actual rendered feedback panel showed the AI's real corrected answer and explanation - not a mock, the literal live model response rendered in the UI.
- Frontend: `npm run test` — 21 passed (2 new: submitting free text from the textarea, and rendering the AI's corrected-answer/explanation in the incorrect-feedback state). `npm run lint` clean, `npm run build` succeeds (still 11 routes - SHORT_ANSWER reuses `/learn` and `/practice`, no new page needed).
- Test users and demo data created during verification were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- Only one exercise type (`SHORT_ANSWER`) uses AI evaluation. `Sentence correction` and `Speaking response` from `project_requirement_document.md`'s exercise-type list remain unbuilt - natural fits for the same `ai_grading.py` bridge once there's UI/audio input to support them (speaking specifically needs Phase 8).
- `score` from the AI is stored in the displayed `correct_answer` payload but isn't otherwise used for partial-credit mastery updates - mastery still updates via the same binary `is_correct` signal every other exercise type uses, keeping `memory.md`'s mastery formula single-purpose rather than conditionally behaving differently per exercise type.
- No per-user or global rate limiting on AI-touching endpoints yet - `phases.md` assigns "AI cost controls" to Phase 12 (Production Hardening) explicitly, so this is deferred on purpose.
- The Groq model choice (`openai/gpt-oss-120b`) is a reasoning model with real per-request latency (~1s observed, mostly reasoning tokens) - fine for a single evaluation call, but worth reconsidering against a faster model if Phase 7's conversational tutor needs lower-latency turn-taking.

## Phase 5 notes

### What was implemented

**Practice sessions**, distinct from lessons: `practice_sessions`/`practice_questions` hold a personalized, cross-lesson set of exercises the recommendation engine selects, rather than one lesson's fixed exercise list in order. `POST /practice/start` creates (or resumes an in-progress) session; `POST /practice/{session_id}/answer` grades it - reusing the exact same `grade_exercise` and `learner_model_service.record_answer_learning_event` machinery lessons use, since a practice answer is just as meaningful a learning event as a lesson answer.

**Recommendation engine** (`app/services/recommendation.py`), implementing `architecture.md` §9's formula deliberately partially: `weakness` (`100 - mastery`) and `recent_mistakes` (incorrect count in the last 5 attempts on that skill) are literal scored terms; `review_due` adds a flat +50 bonus. The other three terms from that formula aren't separate numeric weights, and the module's docstring says so explicitly rather than silently dropping them: `lesson_progress` is structural (candidate skills are scoped to ones with an existing `skill_mastery` row - you can't get personalized practice on a skill you've never touched), `learner_goal` isn't used to size a session dynamically (fixed at up to 5 questions), and `excessive_repetition` is structural too (at most one exercise per skill per session).

**Exercise selection within a chosen skill** (`practice_service._select_exercise_for_skill`): mistake review takes priority - if the learner has ever gotten an exercise for this skill wrong (queried from the unified `learning_events` log, so it covers both lesson and practice history), one of those is re-served. Otherwise, adaptive difficulty picks whichever exercise's static `difficulty` rating (added in Phase 4) is closest to `mastery / 100` - rules.md §4's difficulty-should-track-ability rule, applied at selection time rather than by generating new content.

**Real spaced repetition** (`app/services/spaced_repetition.py`), replacing Phase 4's flat mastery-bucket `next_review_at` with the interval/ease/repetitions fields `memory.md` §9 actually asks for: a simplified SM-2 - correct answers grow the interval (`new_interval = round(stored_interval × ease)`, `ease` nudged up per correct answer, down per miss, floored at 1.3) and grow repetitions; a miss resets repetitions to 0 and drops the interval to 1 day, per rules.md §4 ("do not punish a learner excessively for one difficult question"). New `ease_factor`/`repetitions`/`interval_days` columns on `skill_mastery`.

**Frontend**: `/practice` reuses the exact same `ExerciseRenderer`/`FeedbackPanel` components lessons use (see the type refactor below), with its own empty state ("complete a lesson first") for learners with no history yet. Dashboard links to it.

**Refactor while in the area**: `ExerciseRenderer`/`FeedbackPanel` were typed against the lesson-specific `AnswerResult` (which carries `xp_earned`/`current_streak`/etc. practice doesn't have), which would have forced an awkward field-renaming adapter object every time practice built one. Instead, pulled the three fields those components actually read (`is_correct`, `correct_answer`, `explanation`) into a new `ExerciseFeedback` type that `AnswerResult` extends; practice's `PracticeAnswerResult` satisfies it structurally with zero adapter code.

### A real bug this caught before it shipped

**Unbounded exponential interval growth in spaced repetition.** The first implementation reconstructed a skill's previous interval from `repetitions` and the current `ease_factor` via a loop (`interval = 3; for _ in range(repetitions - 2): interval = round(interval * ease)`), assuming a constant ease across all prior repetitions. In reality ease changes every review, and multiplying by it repeatedly compounds fast: a test that drove 20 consecutive correct answers on one skill raised a genuine `OverflowError: date value out of range` - the projected interval blew past what Python's `datetime` can represent. The fix was two-fold: stop reconstructing history and use the `interval_days` already stored on the row (which is both simpler and actually correct, since it reflects what really happened rather than an approximation), and add a hard cap (`MAX_INTERVAL_DAYS = 365`, since a year is already well past "needs regular review"). A regression test now drives 50 consecutive correct answers and asserts the interval never exceeds the cap.

### Verification performed

- Backend: `pytest -q` - 89 passed (20 new: 6 spaced-repetition unit tests including the exponential-blowup regression, 6 recommendation-engine unit tests including one asserting two different mastery histories literally produce different skill rankings, and 10 practice-flow integration tests against a purpose-built multi-skill fixture - weakest-skill-first ordering, **the exit criteria proven directly** (two users, inverse histories, different first exercises returned), mistake-review overriding difficulty-matching in a scenario specifically constructed so the two mechanisms would disagree, learner-model integration, idempotent resubmission, session completion, resume, and an ownership/403 check). `ruff check .` and `mypy app` clean.
- Manual `curl` walkthrough against the live `lingoadapt_dev` database: completed "Saying Hello" entirely wrong (GREETINGS → mastery 0) and "Introducing Yourself" entirely right (INTRODUCTIONS → mastery 22.1), started a practice session, and confirmed GREETINGS was selected first purely from the priority formula. Confirmed the spaced-repetition interval growth against real data too: after 3 consecutive correct INTRODUCTIONS answers, `next_review_at` had grown 1 → 3 → 8 days out, matching the formula exactly.
- **Browser verification** (Playwright, installed temporarily then removed again): confirmed `/practice`'s honest empty state before any lesson, then confirmed it serves a real, correctly-rendered question after completing a lesson.
- Frontend: `npm run test` - 19 passed (2 new: `practice-api` request/body tests). `npm run lint` clean, `npm run build` succeeds (11 routes now, `/practice` added).
- Test users created during verification were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- A practice session is capped at 5 questions (one per top-ranked skill) - not dynamically sized to the learner's daily XP goal, a deliberate simplification of `architecture.md`'s `learner_goal` term (documented above).
- "Missed before" is permanent, not time-decayed - an exercise flagged as ever-missed stays eligible for mistake-review re-serving indefinitely, even if the learner's mastery on that skill has since recovered. Simple and matches "Mistake review" literally; a recency-weighted version is a reasonable future refinement, not a correctness bug.
- Practice sessions don't award XP or affect streaks - a deliberate scope decision (Phase 3's "Lesson completion rewards" wording ties XP specifically to lessons), not an oversight. They do fully update skill mastery, confidence, and spaced-repetition state.
- Only skills with at least one prior learning event can appear in a practice session - a brand-new learner with zero completed lessons gets an honestly-empty session (`total_count: 0`), not a fallback recommendation. This is intentional (see `lesson_progress`'s handling above), not a missing case.

## Phase 4 notes

### What was implemented

**Data model**: `learning_events` (append-only: user, exercise, skill, correct, difficulty, optional response time - matches `architecture.md` §7's example JSON) and `skill_mastery` (one row per user+skill: mastery, confidence, attempt/correct counts, last-practiced/next-review timestamps, `CHECK` constraints keeping mastery and confidence in `[0, 100]` at the DB level, not just in application code). Also added a `difficulty` column to `exercises` (0-1, static content rating, backfilled to 0.5 for the 31 already-seeded exercises via a migration `server_default`) and set it per-unit in the seed data (0.2 for Greetings ramping to 0.6 for Travel) - `learning_events.difficulty` needed a real signal to record, and this is exactly where architecture.md's example event gets that value from. This is *not* the adaptive difficulty *selection* algorithm (choosing exercises based on estimated ability) - that's explicitly Phase 5.

**Mastery algorithm** (`app/services/mastery.py`), reproducing `memory.md` §8's worked example exactly: `new = old×0.92 + (100 if correct else 0)×0.08` - solved directly from the documented example (old=50, correct→54, incorrect→46). A pure function, no DB, bounded by construction (weighted average of values already in `[0,100]`) and additionally clamped as defense in depth. A brand-new skill starts at mastery 0 (no evidence yet), so `rules.md` §3.9 ("a single correct answer should not imply mastery") holds structurally: one correct answer only reaches 8.

**Confidence** - separate from mastery on purpose: mastery is *what the number is*, confidence is *how much to trust it*. Computed as `min(100, attempts / 10 × 100)` - reaches full confidence after 10 attempts on a skill regardless of how high or low the mastery estimate is.

**Review scheduling**: mastery bucketed into next-review intervals (< 30 → 1 day, < 60 → 3 days, < 80 → 7 days, else → 14 days). Deliberately simple - `phases.md` splits this on purpose: Phase 4 needs the *data* (a `next_review_at` per skill) to satisfy its own exit criteria, while Phase 5's actual spaced-repetition practice queue (ease factors, repetitions) is a separate, later concern that can replace just this function without touching anything upstream.

**Where it hooks in**: `lesson_service.submit_answer` calls `learner_model_service.record_answer_learning_event` once per *fresh* exercise answer (skipped on the idempotent-resubmit path, same pattern as the XP/exercise-attempt logic from earlier phases) - so re-fetching an already-answered exercise never double-counts a learning event or perturbs mastery twice.

**API**: `GET /me/mastery` (every skill the learner has touched: mastery, confidence, level, attempt/correct counts, last-practiced/next-review) and `GET /me/review` (skills currently due, i.e. `next_review_at <= now`) - both matching `architecture.md`'s documented API surface exactly. `level` is a simple threshold classification (`mastery >= 70` → `strong`, `< 40` → `weak`, else `developing`) - this is the literal mechanism behind the phase's exit criteria: *"the system can explain which skills are strong and weak for a learner."*

**Frontend**: new `/progress` page (`design.md` §10's "Progress Page", built now since this is the phase that actually produces the data it needs) - one bar per skill, colored by level, sorted by mastery descending, plus a "Due for review" callout when applicable and an honest empty state before any lesson is completed. Linked from the dashboard's profile card.

### Verification performed

- Backend: `pytest -q` - 69 passed (19 new: 11 pure `mastery.py` unit tests, including two that assert the exact `memory.md` worked-example values (54/46) byte-for-byte, plus 8 integration tests - learning-event creation, mastery matching the formula after a real API call, accumulation across multiple exercise types sharing one skill, idempotent-resubmit not double-counting, `strong` threshold reached via 20 direct service calls (driving the service layer directly here, not the HTTP lesson flow, since a resumed in-progress attempt hits the idempotent no-op path on re-answering the same exercise - documented inline in the test), auth-required checks, and the review-queue date-filtering behavior with a directly backdated row). `ruff check .` and `mypy app` clean.
- Manual `curl` walkthrough against the live `lingoadapt_dev` database: confirmed `/me/mastery` and `/me/review` start empty for a fresh user, then after one correct + one incorrect answer on the same skill, `/me/mastery` showed `attempt_count: 2, correct_count: 1, mastery: 7.4` - matching `8.0 × 0.92 = 7.36` (the exact formula, rounded for display) rather than a made-up number.
- **Browser verification** (Playwright, installed temporarily then removed again, same as every phase so far): signed up, confirmed `/progress` shows the "complete a lesson" empty state before any activity; completed a real lesson with a deliberate mix of one wrong answer among four; confirmed `/progress` then showed the `Greetings` skill with `3 / 4 correct` and an amber (weak/developing) bar - i.e., confirmed the *actual rendered page*, not just the API response, reflects a real mixed-performance history.
- Frontend: `npm run test` - 17 passed (2 new: `mastery-api` request/header tests). `npm run lint` clean, `npm run build` succeeds (9 routes now, `/progress` added).
- Test users created during verification were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- `response_time_ms` on `learning_events` is nullable and currently always `null` - the frontend doesn't yet time how long a learner takes to answer. `project_requirement_document.md` §7 lists this as an *optional* signal, so it's deferred rather than fabricated.
- Skills only accumulate mastery from graded lesson exercises. Free-form/open-ended answer evaluation (Phase 6) and AI conversation (Phase 7) will need their own hooks into `record_answer_learning_event` (or an equivalent) once they exist.
- The review-scheduling buckets are a fixed lookup table, not real spaced repetition (no ease factor, no growing intervals on repeated success) - intentional per the phases.md split described above; Phase 5 is where that gets built.
- No skill-level breakdown by exercise *type* (e.g. "strong at multiple-choice, weak at translation, same skill") - mastery is tracked per skill only, matching `rules.md` §3.3 ("mastery should be skill-specific") and no more granular than that was asked for.

## Phase 3 notes

### What was implemented

**Data model** (migration `843a1c49f90e`): `xp_transactions` (amount, reason, optionally traced back to the `lesson_attempt` that earned it), `streaks` (one row per user: current/longest streak, last-active date), `achievements` (a small fixed catalog), `user_achievements` (join table, `UNIQUE(user_id, achievement_id)` so an achievement can't be double-awarded even under a race). `daily_quests` from `architecture.md`'s table list was deliberately **not** added — that's Phase 9 (Advanced Gamification) scope per `phases.md`, not this one.

**XP formula** (`app/services/gamification_service.py::compute_lesson_xp`): `correct_count × 10`, awarded once per lesson completion — correctness-weighted rather than flat-per-completion, so it can't be farmed by clicking through a lesson without engaging (`rules.md` §8: "XP should correspond to meaningful learning activity"). Isolated in its own function so the formula can be retuned without touching callers.

**Streak logic** (`app/services/streak.py`): a pure function with no DB dependency — same-day revisit is a no-op, a consecutive day increments, any gap of more than one day resets to 1, longest-streak is preserved across a reset. Deliberately simple and swappable later (per-user timezone handling instead of UTC dates, for instance — see limitations).

**Achievement foundation**: 4 achievements (`FIRST_LESSON`, `PERFECT_LESSON`, `STREAK_3`, `XP_100`), each a `(code, name, description, condition_fn)` tuple evaluated deterministically against a small context object (total XP, current streak, lessons completed, was-the-just-finished-lesson-perfect) — no AI involved, matching `rules.md` §2's requirement that rewards be deterministic and server-owned.

**Where rewards get applied**: inside `lesson_service.submit_answer`, in the same DB transaction as the lesson-completing answer — so XP, streak, and achievement rows either commit together with the lesson completion or not at all, never partially. `apply_lesson_completion_rewards` is itself idempotent (checks for an existing XP transaction on that lesson attempt first), as a concurrency safety net; in practice the API's own guard (further answers on a completed attempt return `409`) means this is normally called exactly once per attempt, but the idempotency check is defense in depth, tested directly at the service layer since it isn't reachable through the HTTP API alone.

**API**: `GET /me/progress` (total/today's XP, daily goal, current/longest streak, per-course completion percentage, full achievement list with earned/locked state, recent XP history) and `GET /achievements` (the same achievement list standalone). Both require auth. `POST /exercises/{id}/answer`'s response now also carries `xp_earned`, `current_streak`, and `new_achievements` for the completing answer, so the frontend can show a reward summary without a second round-trip.

**Frontend**: dashboard now shows a daily-goal progress bar, a streak badge, a course-completion bar, and an achievement grid (locked achievements shown dimmed with a 🔒, matching `design.md`'s restrained-rewards guidance rather than a loud unlock animation). The lesson-complete screen shows `+N XP`, the streak badge, and any newly unlocked achievement cards (fetched once, only when `new_achievements` is non-empty, so a page refresh doesn't re-announce an old unlock).

**Refactor while I was in the area**: extracted the `fetch`/`ApiError` wrapper that `auth-api.ts` and `course-api.ts` had each duplicated into a shared `lib/api-client.ts` before adding a third copy for `progress-api.ts` — same behavior, one implementation.

### Verification performed

- Backend: `pytest -q` — 50 passed (15 new: 6 pure unit tests for the streak algorithm covering first-activity/consecutive/same-day/gap-reset/longest-preserved cases with no DB involved, plus 9 integration tests — XP proportional to correct answers, streak set on first activity, zero XP/null streak on an incomplete lesson, both achievements unlocking together on a perfect first lesson, only `FIRST_LESSON` unlocking on an imperfect one, `/me/progress` reflecting a completed lesson end-to-end, auth-required check, `/achievements` listing the full catalog with correct earned flags, and the idempotency safety-net test described above). `ruff check .` and `mypy app` clean.
- Manual `curl` walkthrough against the live `lingoadapt_dev` database: checked `/me/progress` was all-zeros for a fresh user, completed a real lesson perfectly, confirmed the answer response carried `xp_earned: 40`, `current_streak: 1`, and both achievement codes, then confirmed `/me/progress` reflected all of it afterward (`total_xp: 40`, course at `10%`, both achievements `earned: true` with timestamps, one XP-history entry).
- **Browser verification** (Playwright, installed temporarily then removed again): signed up, confirmed the dashboard's daily-goal bar reads `0 / 50 XP` and the achievements section renders before any lesson; completed "Saying Hello" perfectly and confirmed the completion screen shows `+40 XP`, a `1 day` streak badge, and both new-achievement cards (had to explicitly wait for the achievement fetch to resolve — an early screenshot caught the page mid-fetch, same class of timing artifact as Phase 2's, not a bug); navigated back to the dashboard and confirmed the daily-goal bar now reads `40 / 50 XP`, the course bar shows `1 / 10 lessons`, total XP shows `40 XP`, and the achievement grid shows `First Steps`/`Perfectionist` unlocked (amber) alongside `On a Roll`/`Century Club` still locked (dimmed, 🔒).
- Frontend: `npm run test` — 15 passed (2 new: `progress-api` request/header tests, plus an existing `ExerciseRenderer` test fixture updated for the new `AnswerResult` fields). `npm run lint` clean, `npm run build` succeeds.
- Test users created during verification were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- Streak "day" boundaries use UTC dates, not the learner's own timezone — a learner near midnight could see their streak roll over at a time that doesn't match their local day. Fine for now; the streak function is isolated specifically so this is a contained change later.
- The achievement catalog is fixed in code (`ACHIEVEMENT_CATALOG`) and seeded via `python -m app.seed` — no admin UI to add new achievements yet (Phase 10).
- No leaderboards, leagues, virtual currency, or daily quests — all explicitly Phase 9 scope, not built here.
- XP is only awarded for lesson completion. Once Phase 4 (learner model) and Phase 5 (personalized practice) exist, other activities (practice sessions, review) will need their own reward hooks into the same `xp_transactions`/streak machinery.

## Phase 2 notes

### What was implemented

**Data model** (migration `f355827198d0`): `languages`, `courses`, `units`, `lessons`, `skills`, `exercises`, `exercise_options` for content; `lesson_attempts`/`exercise_attempts` for a learner's progress through a lesson. `exercise_options` is one normalized table shared by all five exercise types, with type-conditional columns (`is_correct` for multiple choice, `correct_position` for word order, `match_group`/`match_key` for matching) rather than a separate table per type or an opaque JSON blob — keeps it query-able and admin-tool-friendly later (Phase 10) while staying simple now.

**Grading — fully deterministic, no AI** (`app/services/grading.py`): all five types (multiple choice, fill-in-the-blank, translation, word order, matching) have an objectively correct answer, so grading is plain equality/lookup logic, consistent with `rules.md` §2 ("Use deterministic code... AI is for language understanding/evaluation of free-form input," which these aren't). Free-form/open-ended answer evaluation is Phase 6's job, not this one.

**Lesson flow** (`app/services/lesson_service.py`): `POST /lessons/{id}/start` creates a new attempt, or resumes the existing `IN_PROGRESS` one for that user+lesson (returning which exercises are already answered so the frontend can skip ahead). `POST /exercises/{id}/answer` grades server-side, records the attempt, and marks the lesson `COMPLETED` once every exercise has been answered. Re-submitting an already-answered exercise returns the original recorded result instead of re-grading (idempotent, prevents double-counting). Answering into someone else's attempt is `403`; answering into a completed attempt is `409`.

**Security-relevant design point:** exercises are served via a `ExercisePublicOut` schema that never includes `is_correct`, `correct_position`, or `match_key` — verified by a test that asserts none of those strings appear anywhere in the `/start` response body. The correct answer is only revealed in the response to `/answer`, after grading.

**Seed content** (`app/seed.py`, idempotent): one course, "English Foundations" — 5 units (Greetings, Introductions, Daily Life, Food, Travel), 10 lessons, 31 exercises spanning all 5 types, realistic A1-level content (not lorem ipsum). Run with `python -m app.seed`.

**Frontend:** `/learn` (course/unit/lesson browser), `/learn/[lessonId]` (the lesson runner — progress bar, one exercise at a time, Check → feedback → Continue, ending in a completion screen), plus `components/exercise/` with one input component per type (`ExerciseRenderer` dispatches on `exercise.type`, remounted via `key={exercise.id}` so per-exercise answer state resets cleanly between exercises — same pattern as the Phase 1 settings-form fix). Dashboard's placeholder card now links to the real course.

### Bugs found and fixed via browser verification (not just curl)

Both of these were real defects that unit tests alone wouldn't have caught, since they only manifest in what the API actually returns / how the UI actually uses it:

1. **Word-order and matching options were trivially solvable.** `exercise_options` rows are stored in their correct order/pairing (simplest for the seed script to write). Serializing them to the client in that same order meant a "put these words in order" puzzle already appeared in the correct order, and a "match these pairs" exercise had its right column pre-aligned with the left column by position. Fixed by shuffling in `ExercisePublicOut.from_model` (word-order: shuffle all; matching: shuffle the right column only, keep left stable) — grading still reads the DB-stored `correct_position`/`match_key`, never the display order. Added a regression test asserting the returned option-id *set* is complete regardless of order. Caught by reading the actual API response during the curl-based check, before the browser pass even started.
2. **Lesson-complete screen showed "0 / 4 correct" after actually getting 3/4 right.** The completion screen read `lessonData.correct_count`, a snapshot from the initial `/start` call that never updates as the learner answers exercises. Fixed by tracking a separate `progress` state updated from each `/answer` response's own `correct_count`/`total_count`, which the backend already returns fresh every time. This one only surfaced by actually clicking through a full lesson in a real browser and reading the final screen — nothing about it would show up in a unit test of either side in isolation, since each side was individually "correct" (the API genuinely returns the right count in each response; the frontend genuinely renders whatever field it's given) — the bug was purely in which piece of already-correct data the UI chose to display.

### Verification performed

- Backend: `pytest -q` — 35 passed (19 new: lesson start/resume, grading for all 5 types including case-insensitivity and wrong-order/swapped-pairs negative cases, ownership/completion-state error paths, malformed-input 400s, and the answer-leakage regression test). `ruff check .` and `mypy app` clean.
- Manual `curl` walkthrough against the live `lingoadapt_dev` database with the real seeded course: listed courses, fetched course detail, started "Saying Hello," answered all 4 exercises (one intentionally wrong), confirmed per-type feedback and correct lesson-completion trigger on the last one.
- **Full browser verification** (Playwright, installed temporarily then removed again — see Phase 1 notes on why): signed up, landed on dashboard, clicked through to `/learn`, completed "Saying Hello" (multiple choice, fill-in-blank, translation, word order — one wrong on purpose to see incorrect-feedback styling), then completed "Saying Goodbye" for the matching type specifically (screenshotted mid-flow to confirm the shuffle fix actually shows a reshuffled right column, not just fixed in the API). Both bugs above were caught this way.
- Frontend: `npm run test` — 13 passed (4 new: course-api request/error handling, and `ExerciseRenderer` interaction tests covering the Check-button-disabled-until-valid-answer gating and the Check→Continue transition for both multiple-choice and text-input exercise types). `npm run lint` clean, `npm run build` succeeds (all 8 routes, including the dynamic `/learn/[lessonId]`).
- Test users created during verification were deleted from `lingoadapt_dev` afterward.

### Known limitations / follow-ups

- Course browsing (`/learn`) always shows the first published course, ignoring the learner's `target_language` preference from signup — fine while there's exactly one seed course, but will need real course selection once more than one exists (Phase 10, course authoring).
- No XP, streaks, or progress persistence beyond the lesson-attempt records themselves — that's explicitly Phase 3's scope per `phases.md`, not an oversight here.
- No skill-mastery updates yet from lesson answers (each `exercise_attempt` records `is_correct` and is skill-tagged via its exercise, so the data Phase 4 needs already exists — just not consumed yet).
- Lesson content can't be authored without editing `app/seed.py` and re-running it — Phase 10 adds real admin tooling.

## Phase 1 notes

### What was implemented

**Auth model.** `architecture.md` calls for "Supabase Auth or an equivalent managed auth system." Rather than fabricate Supabase credentials I don't have, I built a self-hosted equivalent using dependencies already scaffolded in Phase 0 (`python-jose`, and now `bcrypt` — see below): short-lived JWT access tokens (15 min) plus a DB-backed, revocable refresh-token session (30 days, httpOnly cookie, rotated on every use). This keeps auth deterministic and server-owned per `rules.md` §2/§3, and is a straightforward swap-in point for Supabase later since it's isolated behind `app/services/auth_service.py`.

**Backend:**
- New tables (migration `b34cb9f9bc58`): `users`, `user_preferences` (native/target language, daily XP goal), `refresh_tokens` (hashed, revocable, expiring).
- `app/core/security.py` — password hashing (bcrypt, direct — see compatibility note below) and JWT create/verify.
- `app/repositories/user_repository.py` — all user/session DB access.
- `app/services/auth_service.py` — signup, login, refresh (rotates the token), logout (revokes it).
- `app/api/v1/auth.py` (`POST /auth/signup|login|refresh|logout`) and `app/api/v1/me.py` (`GET /me`, `PATCH /me/preferences`).
- `app/api/deps.py` — `get_current_user` dependency for protected routes (Bearer JWT).

**Frontend:**
- `lib/auth-context.tsx` — React context; attempts a silent `/auth/refresh` on mount (httpOnly cookie) so a page reload keeps you logged in without re-entering credentials.
- `(auth)/signup`, `(auth)/login`, `dashboard/`, `settings/` pages, matching `architecture.md`'s suggested route layout.
- `hooks/use-require-auth.ts` — redirects to `/login` when unauthenticated.
- Home page (`/`) is now a real landing page (CTA to sign up/log in, auto-redirects to `/dashboard` if already authenticated) — replaces the Phase 0 backend-health status page, which was removed along with its now-dead `lib/api.ts` helper.

**Tests:** `backend/tests/test_auth.py` (15 cases: signup, duplicate email, validation, login success/failure, `/me` auth required, preferences update, refresh, refresh-after-logout) run against a real dedicated Postgres database (`lingoadapt_dev_test`), each wrapped in a rolled-back transaction via SQLAlchemy's `join_transaction_mode="create_savepoint"` so app-level `commit()` calls don't leak between tests. Frontend: `auth-api.test.ts` and `auth-context.test.tsx` cover the request/error-handling layer and the context's state machine (login/logout transitions) with mocked fetch.

### Bugs hit and fixed along the way

- **`passlib` + modern `bcrypt` are broken together.** `passlib`'s bundled bcrypt self-test uses a 130-byte dummy string; `bcrypt>=4.1` raises `ValueError` instead of silently truncating input over 72 bytes, so `passlib.hash("anything")` failed unconditionally. `passlib` is unmaintained (last release 2020), so rather than pin around it, dropped it for the `bcrypt` package directly, with a SHA-256 pre-hash so passwords of any length remain fully significant to bcrypt (a standard, documented workaround for its 72-byte limit).
- **`react-hooks/set-state-in-effect` in `settings/page.tsx`.** Was syncing form state from `user.preferences` via `useEffect`, which the (already-updated) ESLint rule flags as a cascading-render anti-pattern. Fixed by splitting the form into a child component keyed by `user.id` that reads its initial state directly, since the parent already gates rendering until `user` exists — no effect needed.

### Verification performed

- Backend: `pytest -q` (15 passed), `ruff check .` (clean), `mypy app` (clean) — all against real Postgres, not sqlite/mocks.
- Manually drove the full flow with `curl` against the live `lingoadapt_dev` database: signup → `/me` → update preferences → logout → confirmed `/auth/refresh` correctly returns 401 after logout (session actually revoked, not just cookie-cleared client-side).
- **Browser verification** (per the project's UI-testing requirement — this wasn't just curl): started both servers, drove real Chromium via Playwright (installed ad hoc for this, then removed — see below) through landing page → signup → dashboard (correct email/languages/XP shown) → settings → save → confirmed the change persisted back on the dashboard → logout → re-login → dashboard again. Cross-checked against the backend's own access log line-by-line to confirm every request actually landed server-side. No functional issues found; investigated and ruled out one cosmetic `net::ERR_ABORTED` console entry on logout (Chromium's DevTools network-event reporting racing the SPA's client-side redirect after the fetch had already resolved — the server log confirms exactly one logout request per click, always `204`). Added a `disabled`-while-pending guard to the logout button regardless, for consistency with the other forms and as a general double-submit safeguard.
- Frontend: `npm run test` (6 passed), `npm run lint` (clean), `npm run build` (production build succeeds, all 6 routes render).
- Test users created during browser verification were deleted from `lingoadapt_dev` afterward.

Playwright + Chromium were installed temporarily in `frontend/` to drive the browser check above, then uninstalled (`npm uninstall playwright`) since this project has no other use for an E2E framework yet — the chromium binary remains cached locally (`npx playwright install chromium` is fast on a re-run if needed for Phase 2+ UI checks). Worth running `/run-skill-generator` at some point to capture a reusable "run this app in a browser" project skill instead of re-deriving this each phase.

### Known limitations / follow-ups

- No rate limiting on `/auth/login` or `/auth/signup` yet — `phases.md` explicitly assigns rate limiting to Phase 12 (Production Hardening), so this is deferred on purpose, not an oversight.
- Access tokens are returned in the JSON body and expected to be held in memory (React state) rather than `localStorage`, to limit XSS blast radius — but that does mean a hard page refresh briefly shows a loading state while `/auth/refresh` re-establishes the session from the httpOnly cookie. This is intended behavior, not a bug.
- `native_language`/`target_language` are free-standing language-code strings (not FK'd to a `languages` table) — intentional for now; `languages`/`courses` proper arrives in Phase 2's course engine, at which point it's worth revisiting whether these should become foreign keys.

## Phase 0 notes

**Implemented:**
- Backend: FastAPI app with `/` and `/api/v1/health` (liveness) and `/api/v1/health/db` (DB connectivity) endpoints, Pydantic settings, SQLAlchemy engine/session setup, Alembic migration scaffolding (no tables yet — added starting Phase 1+).
- Frontend: Next.js (App Router, TypeScript, Tailwind v4) with a status page that live-checks backend connectivity, Framer Motion installed for later phases.
- Tooling: ruff + mypy (backend), ESLint (frontend), pytest (backend) and Vitest + Testing Library (frontend), all configured and passing.
- `docker-compose.yml` for local Postgres 16 + Redis 7.
- `.github/workflows/ci.yml` running backend and frontend lint/type-check/test (and frontend build) on push/PR.
- `tools/start-redis-windows.ps1` — portable, elevation-free Redis server for local dev when Docker/Memurai aren't available.

**Verified:**
- `pytest -q` in `backend/` — 2 passed.
- `ruff check .` and `mypy app` in `backend/` — clean.
- `npm run test` in `frontend/` — 3 passed.
- `npm run lint` in `frontend/` — clean.
- `npm run build` in `frontend/` — production build succeeds.
- Backend started locally with `uvicorn`; `/`, `/api/v1/health`, and `/api/v1/health/db` all returned 200, the last confirming a real connection to the `lingoadapt_dev` Postgres database.
- `alembic upgrade head` ran cleanly against `lingoadapt_dev` (no-op — no migrations exist yet, expected for Phase 0).
- Portable Redis started via `tools/start-redis-windows.ps1`; verified reachable both with `redis-cli ping` and with Python's `redis` client using `protocol=2` (see the RESP3/`HELLO` compatibility note above).

**Known limitations:**
- Docker Desktop's daemon fails to start in this environment, so `docker compose up -d` is untested here. Postgres and Redis were instead set up natively and are both fully verified; the `docker-compose.yml` path itself should be checked on a machine where the Docker daemon actually starts.
- No database tables exist yet; models and the first migration are added in Phase 1 (auth/user profile).

## Next phase

There isn't one - Phase 12 was the last phase in `phases.md`. All 13 phases (0 through 12) are implemented, tested, and documented below. See [Phase 12 notes](#phase-12-notes)' "Known limitations / follow-ups" for what a real production launch would still need beyond what a single local-dev environment can verify (an actual cloud deploy target, a real error-tracking account, a managed Postgres backup schedule, and so on) - deliberately not fabricated here per this project's standing rule against inventing credentials or external services.
