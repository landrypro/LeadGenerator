#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.preprod"}
MANIFEST=${RELEASE_MANIFEST:-"$ROOT/release-manifest.json"}
COMPOSE_FILE=${COMPOSE_FILE:-"$ROOT/compose.preprod.yaml"}
test -f "$ENV_FILE"
test -f "$MANIFEST"
export PREPROD_ENV_FILE="$ENV_FILE"
python3 "$ROOT/scripts/preprod_release_manifest.py" validate --manifest "$MANIFEST" --env-file "$ENV_FILE"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull app worker migrations
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d postgresql redis
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm database-role-provisioner
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm migrations
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --scale worker=2 app worker caddy
"$ROOT/scripts/preprod-verify-release.sh" "$ENV_FILE" "$MANIFEST"
