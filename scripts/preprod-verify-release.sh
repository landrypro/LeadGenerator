#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=$1
MANIFEST=$2
COMPOSE_FILE=${COMPOSE_FILE:-"$ROOT/compose.preprod.yaml"}
test -f "$ENV_FILE"
test -f "$MANIFEST"
export PREPROD_ENV_FILE="$ENV_FILE"
python3 "$ROOT/scripts/preprod_release_manifest.py" validate --manifest "$MANIFEST" --env-file "$ENV_FILE"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T app python - "$MANIFEST" <<'PY'
import json
import sys
import urllib.request
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
for path in ("/api/health/live", "/api/health/ready"):
    with urllib.request.urlopen(f"http://127.0.0.1:8000{path}", timeout=10) as response:
        if response.status != 200:
            raise SystemExit(f"{path}: HTTP {response.status}")
        report = json.load(response)
    if report["release"]["git_sha"] != manifest["git_sha"]:
        raise SystemExit(f"{path}: SHA de release inattendu")
    if report["release"]["image_digest"] != manifest["image_digest"]:
        raise SystemExit(f"{path}: digest de release inattendu")
print("PREPROD_RELEASE_VERIFIED")
PY
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T worker python -m backend.app.cli.worker health
