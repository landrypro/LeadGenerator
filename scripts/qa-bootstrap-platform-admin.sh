#!/usr/bin/env sh

set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.qa.yaml}"
ENV_FILE="${ENV_FILE:-.env.qa}"

if [ "${BOOTSTRAP_PLATFORM_ADMIN_CONFIRM:-}" != "CREATE_FIRST_PLATFORM_ADMIN" ]; then
    echo "Définissez BOOTSTRAP_PLATFORM_ADMIN_CONFIRM=CREATE_FIRST_PLATFORM_ADMIN pour confirmer." >&2
    exit 1
fi

if [ -z "${BOOTSTRAP_PLATFORM_ADMIN_EMAIL:-}" ] || [ -z "${BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME:-}" ]; then
    echo "BOOTSTRAP_PLATFORM_ADMIN_EMAIL et BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME sont obligatoires." >&2
    exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm \
    -e BOOTSTRAP_PLATFORM_ADMIN_CONFIRM \
    -e BOOTSTRAP_PLATFORM_ADMIN_EMAIL \
    -e BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME \
    app python -m backend.app.cli.bootstrap_platform_admin
