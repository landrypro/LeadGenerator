#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.preprod"}
MANIFEST=${RELEASE_MANIFEST:-"$ROOT/release-manifest.json"}
COMPOSE_FILE=${COMPOSE_FILE:-"$ROOT/compose.preprod.yaml"}
BACKUP_ROOT=${BACKUP_ROOT:-"$ROOT/backups/preprod"}
test -f "$ENV_FILE"
test -f "$MANIFEST"
export PREPROD_ENV_FILE="$ENV_FILE"
python3 "$ROOT/scripts/preprod_release_manifest.py" validate --manifest "$MANIFEST" --env-file "$ENV_FILE"
backup_target=$(awk -F= '/^PREPROD_BACKUP_S3_URI=/{print substr($0, index($0, "=") + 1)}' "$ENV_FILE")
kms_key_id=$(awk -F= '/^PREPROD_BACKUP_KMS_KEY_ID=/{print substr($0, index($0, "=") + 1)}' "$ENV_FILE")
case "$backup_target" in s3://*) ;; *) echo "PREPROD_BACKUP_S3_URI doit être une URI S3." >&2; exit 1 ;; esac
test -n "$kms_key_id" || { echo "PREPROD_BACKUP_KMS_KEY_ID est obligatoire." >&2; exit 1; }
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir="$BACKUP_ROOT/$timestamp"
mkdir -p "$backup_dir"
backup_file="$backup_dir/prospect-preprod-$timestamp.dump"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgresql sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"
cp "$MANIFEST" "$backup_dir/release-manifest.json"
metadata_file="$backup_dir/backup-metadata.json"
python3 - "$backup_file" "$MANIFEST" "$metadata_file" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

backup, manifest, output = map(Path, sys.argv[1:])
release = json.loads(manifest.read_text(encoding="utf-8"))
payload = {
    "schema_version": "p5.1-backup-metadata-v1",
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "backup_file": backup.name,
    "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
    "backup_size_bytes": backup.stat().st_size,
    "git_sha": release["git_sha"],
    "image_digest": release["image_digest"],
    "alembic_revision": release["alembic_revision"],
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
aws s3 cp --only-show-errors --sse aws:kms --sse-kms-key-id "$kms_key_id" "$backup_file" "$backup_target/"
aws s3 cp --only-show-errors --sse aws:kms --sse-kms-key-id "$kms_key_id" "$backup_file.sha256" "$backup_target/"
aws s3 cp --only-show-errors --sse aws:kms --sse-kms-key-id "$kms_key_id" "$backup_dir/release-manifest.json" "$backup_target/"
aws s3 cp --only-show-errors --sse aws:kms --sse-kms-key-id "$kms_key_id" "$metadata_file" "$backup_target/"
printf '%s\n' "$backup_dir"
