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

EXPOSE 8000

# The platform's own load-balancer health check should point at /health
# too where the platform supports configuring that - this HEALTHCHECK is
# a backstop for platforms (or local `docker run`) that just check
# container health generically.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Migrations are run as a separate, explicit step (see
# DEPLOYMENT_RUNBOOK.md) rather than at container start - running them
# automatically here would race if the platform ever starts more than one
# instance at once.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
