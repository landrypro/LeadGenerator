#!/usr/bin/env sh

set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.qa.yaml}"
ENV_FILE="${ENV_FILE:-.env.qa}"
BACKUP_DIR="${BACKUP_DIR:-backups/qa}"

if [ ! -f "$ENV_FILE" ]; then
    echo "$ENV_FILE est introuvable." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/prospect-qa-$(date -u +%Y%m%dT%H%M%SZ).dump"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgresql sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP_FILE"

echo "$BACKUP_FILE"
