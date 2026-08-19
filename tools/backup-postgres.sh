#!/usr/bin/env bash
# Backs up a Postgres database to a timestamped, compressed custom-format
# dump, and deletes local dumps older than RETENTION_DAYS. POSIX/Linux
# counterpart to tools/backup-postgres.ps1 (used in local Windows dev) -
# this is the one meant to run on the production host/cron.
#
# Usage:
#   DATABASE_URL="postgresql://user:pass@host:5432/dbname" ./tools/backup-postgres.sh
#
# Optional env vars:
#   BACKUP_DIR       default: ./tools/backups
#   RETENTION_DAYS   default: 14 (local dumps older than this are deleted
#                    after a successful backup - this is retention for
#                    the *local copy on this host*, not full disaster
#                    recovery; see DEPLOYMENT_RUNBOOK.md for why an
#                    offsite copy still matters for a real beta)

set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required (postgresql://user:pass@host:port/dbname)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

# pg_dump accepts a connection URI directly as its target - no need to
# parse DATABASE_URL apart into host/port/user (psycopg's "+psycopg"
# dialect suffix, if present, must be stripped first - pg_dump doesn't
# understand it, it's a SQLAlchemy-ism).
PG_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DB_NAME="$(basename "${DATABASE_URL%%\?*}")"
OUT_FILE="$BACKUP_DIR/${DB_NAME}-${TIMESTAMP}.dump"

echo "Backing up to $OUT_FILE ..."
pg_dump --format=custom --file="$OUT_FILE" "$PG_URL"

SIZE_KB=$(( $(stat -c%s "$OUT_FILE" 2>/dev/null || stat -f%z "$OUT_FILE") / 1024 ))
echo "Backup complete: $OUT_FILE (${SIZE_KB} KB)"

DELETED=$(find "$BACKUP_DIR" -name "${DB_NAME}-*.dump" -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
  echo "Removed $DELETED backup(s) older than ${RETENTION_DAYS} days."
fi
