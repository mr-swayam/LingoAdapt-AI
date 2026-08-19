# Deployment Runbook — Phase 14

This is a step-by-step guide to deploying the existing, verified application (Phases 0–13 — no new features) for a closed beta of 5–20 real users. Follow it in order. Where a step needs a decision only you can make (which platform, what secrets), it says so explicitly.

**When you're done**, send me: the live backend URL, the live frontend URL, and confirmation of which steps you completed. I'll then run an independent verification pass against the real, live URLs (real HTTP requests — no account access needed on my end) and write `PRODUCTION_DEPLOYMENT_REPORT.md` from what I actually observe, not from what this runbook claims should happen.

---

## 0. What's already done (this session, verified locally)

- **Dependency vulnerability scan** — `pip-audit` (backend) and `npm audit` (frontend) both run for real.
  - Frontend: **0 vulnerabilities.**
  - Backend: **1 finding** — `ecdsa` 0.19.2, a timing side-channel in ECDSA signing (PYSEC-2026-1325), pulled in transitively by `python-jose`. This app only uses HS256 (HMAC) JWTs, never ECDSA, so the vulnerable code path is never executed. Classified **LOW**. No upstream fix exists (`python-ecdsa` has stated side-channel attacks are out of scope). No action taken — documented, not suppressed silently.
- **`/health` endpoint** added (`GET /health`) — checks real Postgres and Redis connectivity, returns 503 if the database is down (Redis failure is reported but doesn't fail the check, matching the rate limiter's existing fail-open design). Tested.
- **Error monitoring wiring** added (`app/core/monitoring.py`) — a safe no-op until `SENTRY_DSN` is set; when set, initializes Sentry with FastAPI auto-instrumentation. Tested both branches.
- **Backend `Dockerfile`** — built and run for real against this machine's live Postgres/Redis (via `host.docker.internal`), confirmed `/health` and `/api/v1/courses` both work correctly from inside the container, and confirmed the production config fail-fast (bad `SECRET_KEY`/`CORS_ORIGINS`) correctly refuses to start inside the container too.
- **`tools/backup-postgres.sh` / `tools/restore-postgres.sh`** (Linux/production counterparts to the existing Windows-only `.ps1` versions) — both run for real: backed up the real dev database, restored it into a scratch database, and confirmed row counts matched across 6 tables before cleaning up.
- **`.env.production.example`** — a filled-in-the-blanks template for every environment variable production needs.

None of this required an external account. Everything past this point does, and is yours to execute.

---

## 1. Choose your hosting

**Recommended (simplest for a 5–20 user beta):**

| Component | Recommendation | Why |
|---|---|---|
| Backend | **Railway** (or Render/Fly.io — all support the `Dockerfile` already in `backend/`) | Docker-native, one-click managed Postgres + Redis add-ons in the same project, generous free/hobby tier, simple CLI |
| Database | Railway's managed Postgres add-on | Same project as the backend, one less account to manage |
| Redis | Railway's managed Redis add-on | Same reasoning |
| Frontend | **Vercel** | Built by the maintainers of Next.js, zero-config for this repo's `frontend/` app, automatic HTTPS, generous free tier |
| Error monitoring | **Sentry** (free tier) | Optional but recommended; the code is already ready for it |

**Alternative** if you already have a VPS: `docker-compose.yml` in the repo root already defines Postgres + Redis for local dev — a production variant would add the backend as a third service using `backend/Dockerfile`, plus a reverse proxy (Caddy or nginx) in front of it for HTTPS via Let's Encrypt. This runbook assumes the Railway/Vercel path below; ask me for the docker-compose variant if you're going the VPS route instead — it's a smaller change than it sounds, but the exact steps differ enough that I'd rather write them for your specific setup than have you adapt generic ones.

Either way: **no Kubernetes, no microservices split** — this stays exactly the modular monolith it already is, just running somewhere real.

---

## 2. Generate your production secret key

Do **not** reuse the development placeholder. Generate a real one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Save this somewhere safe (a password manager) — you'll paste it into your host's environment variable UI in step 5. Never put it in a file that gets committed.

---

## 3. Provision Postgres

On Railway: **New Project → Add Database → PostgreSQL**. Copy the connection string it gives you — it'll look like `postgresql://postgres:PASSWORD@HOST:PORT/railway`.

**Important**: this app's `DATABASE_URL` needs the `+psycopg` dialect suffix that Railway's connection string won't include by itself. Change:
```
postgresql://postgres:PASSWORD@HOST:PORT/railway
```
to:
```
postgresql+psycopg://postgres:PASSWORD@HOST:PORT/railway
```

## 4. Provision Redis

On Railway: **same project → Add Database → Redis**. Copy the connection string (`redis://default:PASSWORD@HOST:PORT`).

The app defends itself if Redis is briefly unreachable (rate limiting fails open — see `app/core/rate_limit.py`), so this isn't a single point of failure for the whole app, only for rate limiting specifically, while it's down.

## 5. Configure the AI provider

Use a **separate Groq API key from your development one** if you can — that way production usage doesn't count against (or get disrupted by rotating) whatever key you've been using locally all session. Get one at [console.groq.com](https://console.groq.com).

If you plan to use voice features (Phase 8 — SPEAKING/LISTENING exercises, voice tutor messages), the TTS model needs one-time terms acceptance by the account owner at:
`https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english`
— do this once before beta users hit those features, or they'll get a real (safely-handled, but avoidable) AI-provider error.

## 6. Deploy the backend

On Railway: **same project → New Service → Deploy from GitHub repo** (or `railway up` from the `backend/` directory if you'd rather use the CLI). Point it at the `backend/` directory (it'll find the `Dockerfile` there automatically).

Set these environment variables in Railway's dashboard for this service (use `.env.production.example` as your checklist):

```
ENVIRONMENT=production
DATABASE_URL=<from step 3, with +psycopg>
REDIS_URL=<from step 4>
SECRET_KEY=<from step 2>
CORS_ORIGINS=<leave this as a placeholder for now - https://placeholder.vercel.app - you'll update it in step 9 once you know your real Vercel URL>
AI_PROVIDER=groq
AI_API_KEY=<from step 5>
AI_DEFAULT_MODEL=openai/gpt-oss-120b
SENTRY_DSN=<from step 10, or leave blank for now>
```

Deploy. Railway will build the Docker image and give you a public URL like `https://your-service.up.railway.app`.

**Verify it started** (don't skip this): once deployed, run
```bash
curl https://your-service.up.railway.app/health
```
You should get `{"status":"ok","checks":{"database":"ok","redis":"ok"}}`. If `database` or `redis` says `"unreachable"`, double-check the connection strings from steps 3–4 (most common mistake: forgetting `+psycopg`, or a stray trailing slash).

## 7. Run migrations against the production database

From your own machine, with the production `DATABASE_URL` (from step 3):

```bash
cd backend
DATABASE_URL="postgresql+psycopg://...production connection string..." \
  .venv/Scripts/alembic.exe upgrade head    # Windows, this repo's venv
# or, from a plain shell with alembic installed:
DATABASE_URL="postgresql+psycopg://...production connection string..." alembic upgrade head
```

This was already verified reproducible from a completely empty database during Phase 13 (all 12 migrations applied cleanly, zero drift from the models) — this step is just running that same, already-proven chain against the real production database instead of a throwaway one.

**Do this once.** Don't put migrations in the container's startup command — see the comment in `backend/Dockerfile` for why (race risk if the platform ever runs more than one instance).

## 8. Promote yourself to admin (production)

There's deliberately no self-serve way to become an admin (rules.md — authorization is server-owned, deterministic state). Once you've signed up a real account on the deployed app:

```bash
DATABASE_URL="postgresql+psycopg://...production..." \
  python -m app.promote_admin your-real-email@example.com
```

Run this from your own machine (or Railway's shell/one-off command feature), same as `promote_admin.py` already works locally.

## 9. Deploy the frontend

On Vercel: **Add New Project → Import your GitHub repo**. Set the **root directory to `frontend/`**. Set this environment variable:

```
NEXT_PUBLIC_API_BASE_URL=https://your-service.up.railway.app/api/v1
```
(your real Railway URL from step 6, with `/api/v1` appended)

Deploy. Vercel gives you a URL like `https://your-app.vercel.app`, with HTTPS automatic.

## 10. Close the loop on CORS

Now that you know your real Vercel URL, go back to Railway and update the backend's `CORS_ORIGINS` environment variable to your real frontend URL (no trailing slash):

```
CORS_ORIGINS=https://your-app.vercel.app
```

Redeploy the backend service for this to take effect. This is the one genuinely circular step in this whole process (frontend needs the backend URL, backend's CORS needs the frontend URL) — there's no way around doing it in two passes.

## 11. Set up error monitoring (recommended, optional)

Create a free project at [sentry.io](https://sentry.io) (choose "FastAPI" as the platform when it asks). Copy the DSN it gives you. Set `SENTRY_DSN` on the Railway backend service, redeploy. That's the entire integration — `app/core/monitoring.py` does the rest automatically once the env var is present.

## 12. Set up automated backups + retention

`tools/backup-postgres.sh` (already tested this session against a real database) needs to run on a schedule against your production `DATABASE_URL`. The simplest option that needs no new infrastructure: a **scheduled GitHub Actions workflow** in this repo, using a `DATABASE_URL` repository secret (set via GitHub's UI — never commit it) and uploading the resulting dump as a workflow artifact (or to cheap object storage if you want it to outlive GitHub's artifact retention window). I've deliberately not added this workflow file myself — it needs your production `DATABASE_URL` as a GitHub secret, which is a credential-configuration step only you should do. Once you've added the secret, tell me and I'll write the workflow file itself (that part doesn't need your credentials, just needs to know the secret's name).

Retention: `RETENTION_DAYS` (default 14) controls how many days of *local* dumps the script keeps on whatever disk it runs on. For real disaster-recovery value, dumps should also land somewhere that survives the backup host disappearing — even a cheap object-storage bucket is enough for a 5–20 user beta. Exact wiring depends on which you choose; ask me once you have one and I'll adjust the script's upload step.

## 13. Test the restore procedure — WITHOUT touching production

**Never restore-test against the live database.** Always restore into a scratch database, exactly like the two drills already run locally this session:

```bash
DATABASE_URL="postgresql+psycopg://...production connection string, DBNAME REPLACED with a scratch name..." \
  ./tools/restore-postgres.sh path/to/your/backup.dump
```

Most managed Postgres providers let you create an extra scratch database in the same instance for this (Railway: `railway connect postgres`, then `CREATE DATABASE scratch_restore_test;`, then point `DATABASE_URL` at `scratch_restore_test` for the restore command above). Compare a few real row counts between production and the restored scratch database (`SELECT count(*) FROM users;` etc.), then drop the scratch database.

---

## 14. Verification checklist (run these yourself, or send me the URLs and I'll run them)

Once steps 6–10 are done, these should all be true. If you want to run them yourself:

```bash
# Health
curl -i https://your-backend-url/health
# expect: 200, {"status":"ok",...}

# HTTPS is enforced (most PaaS providers do this by default - confirm it)
curl -i http://your-backend-url/health
# expect either a redirect to https://, or the platform to not serve plain HTTP at all

# CORS reflects your real frontend origin, not localhost
curl -i -H "Origin: https://your-app.vercel.app" https://your-backend-url/api/v1/courses
# expect an Access-Control-Allow-Origin header matching your frontend origin

# Request-ID logging
curl -i https://your-backend-url/api/v1/courses
# expect an X-Request-ID header on the response

# Rate limiting is live (11th signup attempt in under a minute from one IP should 429)
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST https://your-backend-url/api/v1/auth/signup \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"ratelimit-check-$i@example.com\",\"password\":\"correct-horse-battery-staple\",\"native_language\":\"en\",\"target_language\":\"es\",\"daily_goal_xp\":50}"
done
# expect: 201 ten times, then 429 on the 11th
```

I'd rather run the full checklist myself against your real URLs once they exist — I can verify signup/login, a full lesson-completion flow, mastery updates, personalized practice, the AI tutor, AI failure handling, and unauthorized-access rejection for real, the same way I verified all of this locally in Phase 13, just pointed at production instead of localhost. **Send me the live backend and frontend URLs when you're ready and I'll do that pass and write `PRODUCTION_DEPLOYMENT_REPORT.md` from what I actually observe.**

---

## Rollback

- **Backend**: Railway keeps previous deployments — redeploy the last known-good one from its dashboard/CLI (`railway rollback` or the dashboard's deployment history). Takes effect in under a minute.
- **Frontend**: Vercel keeps every deployment and lets you "Promote to Production" any previous one instantly from its dashboard — effectively instant rollback.
- **Database**: if a migration causes a problem, `alembic downgrade -1` reverses the most recent migration (every migration in this repo has a `downgrade()`, verified as part of the standard migration-authoring pattern used all session). For data-level problems (not schema), restore from the most recent backup per step 13's procedure, into the *real* database this time (not a scratch one) — this is the one operation in this whole runbook that's genuinely destructive, so double-check the target database name before running it for real.

---

## When you're done

Reply with:
1. The live backend URL.
2. The live frontend URL.
3. Which of steps 1–13 you completed (all of them, ideally, but tell me if anything's still pending — e.g., backups scheduled but Sentry skipped for now).

I'll then run a real verification pass against the live URLs and write `PRODUCTION_DEPLOYMENT_REPORT.md`.
