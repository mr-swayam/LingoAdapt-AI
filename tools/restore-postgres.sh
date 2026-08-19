#!/usr/bin/env bash
# Restores a Postgres custom-format dump produced by backup-postgres.sh.
# Restores with --clean --if-exists (drops/recreates each object it's
# about to restore) but does NOT drop the target database first - point
# this at a fresh/scratch database for a true restore drill (see
# DEPLOYMENT_RUNBOOK.md's restore-drill procedure), not at the live
# database, unless you are intentionally recovering from data loss.
#
# Usage:
#   DATABASE_URL="postgresql://user:pass@host:5432/dbname" \
#     ./tools/restore-postgres.sh path/to/backup.dump

set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required (postgresql://user:pass@host:port/dbname)" >&2
  exit 1
fi
if [ $# -lt 1 ]; then
  echo "Usage: DATABASE_URL=... $0 <dump-file>" >&2
  exit 1
fi

DUMP_FILE="$1"
if [ ! -f "$DUMP_FILE" ]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  exit 1
fi

PG_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"

echo "Restoring $DUMP_FILE into $(basename "${DATABASE_URL%%\?*}") ..."
pg_restore --dbname="$PG_URL" --clean --if-exists --no-owner "$DUMP_FILE"
echo "Restore complete."
