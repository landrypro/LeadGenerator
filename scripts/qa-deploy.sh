#!/usr/bin/env sh

set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.qa.yaml}"
ENV_FILE="${ENV_FILE:-.env.qa}"

if [ ! -f "$ENV_FILE" ]; then
    echo "$ENV_FILE est introuvable. Copiez .env.qa.example puis renseignez les secrets." >&2
    exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build app
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" stop app caddy
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d postgresql redis mailpit
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm database-role-provisioner
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm migrations
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d app caddy
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
