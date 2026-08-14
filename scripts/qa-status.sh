#!/usr/bin/env sh

set -eu

COMPOSE_FILE="${COMPOSE_FILE:-compose.qa.yaml}"
ENV_FILE="${ENV_FILE:-.env.qa}"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T app python - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready", timeout=5) as response:
    print(json.dumps(json.load(response), indent=2, ensure_ascii=False))
PY
