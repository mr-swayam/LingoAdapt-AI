# Production Deployment Report — Phase 14

**Date**: 2026-08-21
**Scope**: deploy the existing, Phase-13-validated application to a real production environment for a closed beta of 5–20 users. No product features were added — every change in this phase is deployment configuration, production hardening, or a bug fix found by deploying and verifying for real.

Every claim below was checked against the actual live deployment (real HTTPS requests to the real URLs, real database queries against the real production database) — not assumed from local behavior. Several real bugs surfaced specifically *because* this was a genuine cross-network deployment (frontend and backend on different domains, behind a real reverse proxy) that no amount of local testing could have caught; each is documented with the real evidence that found it.

---

## 1. Deployment architecture

Unchanged modular monolith, matching the existing architecture — no microservices, no Kubernetes, nothing introduced that wasn't already in the design:

```text
┌─────────────────┐         HTTPS          ┌──────────────────────┐
│  Vercel          │ ─────────────────────► │  Railway              │
│  Next.js frontend│  NEXT_PUBLIC_API_BASE  │  FastAPI backend       │
│  (static + SSR)  │ ◄───────────────────── │  (Docker, single svc) │
└─────────────────┘   CORS-restricted        └──────┬───────┬───────┘
                                                       │       │
                                          private net  │       │  private net
                                                       ▼       ▼
                                              ┌─────────────┐ ┌──────────┐
                                              │ Postgres 18  │ │  Redis    │
                                              │ (Railway)    │ │ (Railway) │
                                              └─────────────┘ └──────────┘
                                                       ▲
                                              public proxy (password-auth)
                                                       │
                                          ┌────────────┴────────────┐
                                          │ GitHub Actions (cron)     │
                                          │ tools/backup-postgres.sh  │
                                          │ → workflow artifact       │
                                          └───────────────────────────┘
```

Backend and database/Redis communicate over Railway's private network (`*.railway.internal`) in normal operation. The public Postgres proxy exists only so the scheduled backup (running on GitHub's infrastructure, outside Railway's network) can reach it — see §9 Remaining Risks.

## 2. URLs

| | |
|---|---|
| Frontend | `https://lingo-adapt-ai.vercel.app` |
| Backend | `https://lingoadapt-ai-production.up.railway.app` |
| Backend health check | `https://lingoadapt-ai-production.up.railway.app/health` |
| Source | `https://github.com/mr-swayam/LingoAdapt-AI` |

## 3. Database configuration

- **Railway-managed PostgreSQL 18**, private hostname `postgres.railway.internal` for the backend service; a public TCP proxy (`altaria.proxy.rlwy.net:<port>`) exists for backup/migration access from outside Railway.
- All 12 migrations applied from empty → current schema (29 tables). An `alembic revision --autogenerate` diff against the migrated production database came back empty, confirming zero drift between the SQLAlchemy models and what's actually deployed.
- Seeded with the same "English Foundations" course used throughout local verification (idempotent `app.seed`, safe to re-run): 5 units, 10 lessons, 34 exercises, 7 achievements. Confirmed live via `GET /api/v1/courses`.

## 4. Redis configuration

Railway-managed Redis, private hostname, used for rate limiting (Phase 12). `/health` confirms live connectivity (`checks.redis: "ok"`). Rate limiting fails open if Redis is ever unreachable (by design, defense-in-depth — see `app/core/rate_limit.py`), so a Redis outage degrades to "no rate limiting" rather than an outage of the app itself.

## 5. AI configuration

- Provider: Groq, model `openai/gpt-oss-120b`.
- A real, live tutor conversation was run against production and returned a real, correctly-classified grammar correction (`PAST_TENSE`) — confirmed the API key, model name, and the whole AI pipeline (metering, cost controls, schema validation) all work end-to-end in the deployed environment, not just locally.

## 6. Environment variables required

See `.env.production.example` for the full annotated list. Summary of what's actually configured on each platform:

**Railway (backend)**: `ENVIRONMENT=production`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` (freshly generated, 64 random bytes, never committed), `CORS_ORIGINS` (the real Vercel origin), `AI_PROVIDER=groq`, `AI_API_KEY`, `AI_DEFAULT_MODEL`, `SENTRY_DSN`.

**Vercel (frontend)**: `NEXT_PUBLIC_API_BASE_URL` (the real Railway backend URL + `/api/v1`).

**GitHub Actions (backup workflow)**: `PROD_DATABASE_URL` repository secret.

No `.env` file was ever committed; all of the above live only in each platform's own secrets/variables store.

## 7. Security controls

- **Startup fail-fast** (unchanged from Phase 12/13, re-verified inside the real container): the app refuses to boot with the default placeholder `SECRET_KEY`, or with a `localhost` origin in `CORS_ORIGINS`, when `ENVIRONMENT=production`.
- **HTTPS**: verified for real — valid TLS certificates confirmed on both `lingoadapt-ai-production.up.railway.app` and `lingo-adapt-ai.vercel.app` via a direct TLS handshake, not just "the platform probably handles it."
- **CORS**: restricted to the real frontend origin; verified via a real cross-origin request showing the correct `Access-Control-Allow-Origin` header.
- **Rate limiting**: 10/minute per IP on auth endpoints, 30/hour per user on AI endpoints. The auth limit was driven to a real 429 in production (see §10 for the real bug this surfaced and fixed).
- **AI cost controls**: the 2000-character cap on free-form input was verified for real — a 3000-character tutor message was rejected with a 422 before any AI provider call was made (confirmed via `ai_call_logs` staying unaffected).
- **Unauthorized access**: `GET /api/v1/me` and `GET /api/v1/admin/courses` both correctly return 401 without a token, verified against the live deployment.
- **Error monitoring**: Sentry initialized in production - confirmed via the real deploy log line `error_monitoring_initialized environment=production`.
- **Request-ID correlation**: confirmed present (`X-Request-ID` header) on real production responses.
- **Dependency vulnerability scan**: `pip-audit` (backend) and `npm audit` (frontend), both run for real, including a re-scan after adding `sentry-sdk` this phase.
  - Frontend: **0 vulnerabilities.**
  - Backend: **1 finding**, `ecdsa` 0.19.2 (PYSEC-2026-1325, a Minerva timing side-channel in ECDSA signing), pulled in transitively by `python-jose`. This app signs JWTs with HS256 (HMAC) only, never ECDSA — the vulnerable code path is never executed. No upstream fix exists (`python-ecdsa` has stated side-channel attacks are out of scope). **Classified LOW**, documented rather than silently suppressed.

## 8. Backup strategy

- `tools/backup-postgres.sh` / `restore-postgres.sh` (Linux/POSIX, added this phase alongside the pre-existing Windows `.ps1` versions).
- **Automated**: `.github/workflows/backup.yml` runs daily (03:00 UTC) plus on-demand (`workflow_dispatch`), dumping the production database and storing it as a GitHub Actions artifact with **30-day retention**. Confirmed running successfully for real after one fix (see §10).
- **Restore procedure documented and tested twice against real production data**: backed up production, restored into a disposable scratch database (`railway_restore_drill`), compared row counts across 7 tables (all matched exactly: languages, courses, units, lessons, skills, exercises, achievements), then dropped the scratch database. The live production database was never modified by either drill.
- A real version-mismatch was caught during this: Railway's Postgres is version 18, but the locally-installed `pg_dump`/`pg_restore` were version 17 and correctly refused to operate against a newer server. Worked around using a matching `postgres:18-alpine` Docker image rather than upgrading local tooling — the same approach the backup *workflow* uses, for consistency.

## 9. Monitoring

- **Sentry** (FastAPI integration, `traces_sample_rate=0.1`) — confirmed initialized in production logs.
- **Structured request logging** (Phase 12, unchanged) — every request gets an `X-Request-ID`, logged with method/path/status/duration; unhandled exceptions are logged with full tracebacks server-side while returning a clean, non-leaking response to the client.
- **`/health`** — checks real Postgres and Redis connectivity (not just "the process is running"), suitable for a platform's own health-check/alerting integration if configured.

## 10. Real bugs found and fixed during this deployment

Eight genuine issues surfaced by actually deploying and verifying — none of these were visible in any of the extensive local testing across Phases 0–13, because each depends on something only a real cross-network production deployment exercises (a real reverse proxy, real separate domains, a real newer Postgres version, etc.). All are fixed and re-verified; none remain open.

| # | Bug | How it was found | Fix |
|---|---|---|---|
| 1 | Backend Dockerfile hardcoded port 8000; Railway routes to a dynamically-assigned `$PORT` | Real 502 "Application failed to respond" immediately after first deploy | `CMD` now reads `$PORT` (defaulting to 8000 for local `docker run`); also fixed to `exec` so the app runs as PID 1 for correct signal handling on redeploy |
| 2 | `DATABASE_URL` picked up a trailing newline pasted into Railway's UI → `FATAL: database "railway\n" does not exist` | Real error from production logs | Enabled `str_strip_whitespace` on all settings - self-healed the existing value without needing it re-entered, and defends every string setting against this class of paste artifact going forward |
| 3 | A TCP Proxy got accidentally added to the *backend* service (instead of Postgres) targeting port 5432, confusing which port the container should bind | Real 502 again after the port-env-var fix, traced via Railway deploy logs showing `Uvicorn running on http://0.0.0.0:5432` | Removed via Railway's UI (operational fix, not code) |
| 4 | Session didn't survive a fresh page load once frontend (Vercel) and backend (Railway) were on different domains - refresh cookie was `SameSite=Lax`, which browsers never send on cross-site `fetch()` calls | Real browser-driven production smoke test: login worked, but `/practice` bounced back to `/login` | `SameSite=None` (paired with `Secure`, as browsers require) outside development; kept `Lax` for local dev where it isn't needed |
| 5 | Auth rate limiting (10/min/IP) never triggered in production - `request.client.host` reflects Railway's reverse-proxy connecting IP, not the real client's, and apparently varied per request | Real test: 11 signups from one machine, expected a 429 on the 11th, got 201 every time | Read the first hop of `X-Forwarded-For` (which Railway's edge sets/overwrites, so it can't be spoofed by a client in this deployment) before falling back to `request.client.host` |
| 6 | Scheduled backup workflow's first real run failed | User reported the failed run | `pg_dump` doesn't understand the `+psycopg` SQLAlchemy dialect suffix the `PROD_DATABASE_URL` secret was set with; normalized the URL in the workflow itself, matching what the `.sh` scripts already did |
| 7 | Local `pg_dump`/`pg_restore` (v17) refused to operate against Railway's Postgres (v18) | Real error on the first backup-drill attempt: `aborting because of server version mismatch` | Used a matching `postgres:18-alpine` Docker image instead of upgrading local client tools |
| 8 | Leftover Phase-0 scaffolding (`app/api/v1/health.py`, a shallower unused duplicate of the real `/health`) | Found reviewing the diff before the first commit | Removed, along with its dead test |

## 11. Smoke-test results (real, against the live deployment)

All of the following were executed against the actual production URLs, not localhost:

- ✅ Signup → real access token issued, redirected to dashboard
- ✅ Session persists across page loads (post-fix #4)
- ✅ Full lesson flow: correct answer graded correctly, incorrect answer graded correctly, lesson completed, **30 XP** awarded
- ✅ Mastery visible immediately after lesson completion
- ✅ Personalized practice returns real exercises
- ✅ AI Tutor: real Groq call, real grammar correction detected and classified
- ✅ AI cost control: oversized input rejected (422) before any AI call
- ✅ Unauthorized access rejected (401) on protected endpoints
- ✅ Rate limiting: real 429 after exactly 10 requests/minute/IP (post-fix #5)
- ✅ HTTPS/TLS valid on both domains
- ✅ Request-ID header present on real responses
- ✅ Error monitoring initialized (Sentry, confirmed via real logs)
- ✅ Real database backup + real restore drill, twice, into disposable scratch databases - production never touched
- ✅ Scheduled backup automation confirmed succeeding for real (post-fix #6)
- Backend: 297/297 automated tests passing, `ruff`/`mypy` clean, before deployment
- Frontend: 49/49 automated tests passing, `eslint`/`tsc`/production build clean, before deployment

## 12. Known issues / remaining risks

| Issue | Classification |
|---|---|
| Public Postgres TCP proxy must stay enabled for the GitHub Actions backup workflow to reach the database (GitHub's runners aren't on Railway's private network) - a real internet-facing surface, mitigated only by a strong random password | **MEDIUM** |
| The real Postgres password was shared in this chat's conversation history during troubleshooting | **MEDIUM** - rotate it via Railway once convenient; nothing indicates it was compromised, this is precautionary |
| AI hourly rate limit (30/user) wasn't driven to its real limit in production (would cost 31 real paid Groq calls to prove) - relies on the identical code path already covered by dedicated automated tests | **LOW** |
| No forced real AI-provider failure (timeout/malformed response) against live production - would require deliberately degrading the real API key, a risk of its own; already covered by dedicated automated tests against this exact, unchanged code | **LOW** |
| No custom domain - using platform-provided subdomains (`*.up.railway.app`, `*.vercel.app`) | **LOW** (fine for a closed beta) |
| Backup retention is 30 days via GitHub artifact expiry only, no secondary/offsite copy | **LOW** (acceptable at this scale; revisit before a larger launch) |
| No dependency vulnerability scan is run automatically/repeatedly - this phase's scan was a one-time manual check | **LOW** |
| Everything else this report checked | **NO ISSUE** |

No BLOCKER or HIGH severity issues remain open.

## 13. Rollback procedure

- **Backend**: Railway retains previous deployments - redeploy the last known-good one from the Deployments tab/CLI. Sub-minute.
- **Frontend**: Vercel retains every deployment - "Promote to Production" any previous one instantly from its dashboard.
- **Database schema**: every migration in this repo has a working `downgrade()` (established convention, not newly claimed) - `alembic downgrade -1` reverses the most recent one.
- **Database data**: restore from the most recent backup (§8's procedure), pointed at the real database this time rather than a scratch one - the one genuinely destructive operation in this whole runbook, so double-check the target database name before running it for real.

## 14. Beta-readiness status

**Can 5–20 real beta users safely use this application right now?**

**YES.**

The only blocker identified in `RELEASE_CANDIDATE_REPORT.md` (Phase 13) - "no production deployment target exists" - is resolved: the application is live, migrated, seeded with real content, and has been verified end-to-end against the actual deployed URLs, not just assumed to work from local behavior. Eight real bugs were found specifically by deploying for real and are all fixed and re-verified. No BLOCKER or HIGH issues remain. The remaining MEDIUM items (public backup-proxy exposure, an already-shared password pending rotation) are real but bounded, don't affect learner-facing functionality, and are reasonable to carry into a small, trusted closed beta while being addressed in parallel.
