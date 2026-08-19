# Production image for the FastAPI backend (Phase 14). Single service,
# matching the existing modular-monolith architecture - no multi-stage
# microservice split, just a lean runtime image.

FROM python:3.12-slim

WORKDIR /app

# curl only - used by the HEALTHCHECK below, not by the app itself.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir .

# Most PaaS hosts (Railway included) route external traffic to a port THEY
# choose at deploy time, passed in via a $PORT env var - a container that
# only listens on a hardcoded port gets a 502 ("application failed to
# respond") even though it's running fine internally. Default to 8000 for
# local `docker run`/docker-compose, where nothing sets $PORT.
ENV PORT=8000
EXPOSE 8000

# Shell form (no brackets) on both of the below so $PORT actually expands -
# JSON-array exec form does not perform shell substitution.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

# Migrations are run as a separate, explicit step (see
# DEPLOYMENT_RUNBOOK.md) rather than at container start - running them
# automatically here would race if the platform ever starts more than one
# instance at once.
#
# JSON-array CMD wrapping `sh -c` (rather than bare shell-form CMD) so
# Docker doesn't warn about OS-signal handling - `exec` inside replaces
# the shell with uvicorn as PID 1, so SIGTERM from a platform redeploy
# reaches uvicorn directly for a graceful shutdown instead of being
# swallowed by an intermediate shell process.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
