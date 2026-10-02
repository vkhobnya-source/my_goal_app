#!/bin/sh

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

until pg_isready \
    --host="$PGHOST" \
    --port="${PGPORT:-5432}" \
    --username="$PGUSER" \
    --dbname="$PGDATABASE"; do
    echo "Waiting for PostgreSQL at $PGHOST:${PGPORT:-5432}..."
    sleep 2
done

while true; do
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup_file="$BACKUP_DIR/goals_${timestamp}.dump"

    echo "Creating PostgreSQL backup: $backup_file"
    pg_dump \
        --host="$PGHOST" \
        --port="${PGPORT:-5432}" \
        --username="$PGUSER" \
        --dbname="$PGDATABASE" \
        --format=custom \
        --file="$backup_file"

    find "$BACKUP_DIR" -type f -name 'goals_*.dump' \
        -mtime "+$BACKUP_RETENTION_DAYS" -delete

    echo "Backup completed. Next backup in ${BACKUP_INTERVAL_SECONDS}s."
    sleep "$BACKUP_INTERVAL_SECONDS"
done
