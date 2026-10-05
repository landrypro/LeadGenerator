#!/usr/bin/env sh
set -eu
backup_file=$1
postgres_image=${POSTGRES_IMAGE:-postgres:17.10-alpine}
test -f "$backup_file"
test -f "$backup_file.sha256"
sha256sum -c "$backup_file.sha256"
container_name="marketteo-preprod-restore-$(date +%s)-$$"
temp_password=$(openssl rand -hex 32)
cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
docker run -d --rm --name "$container_name" -e POSTGRES_PASSWORD="$temp_password" "$postgres_image" >/dev/null
for _ in $(seq 1 30); do
  if docker exec "$container_name" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$container_name" pg_isready -U postgres >/dev/null
docker cp "$backup_file" "$container_name:/restore.dump"
docker exec "$container_name" sh -c 'createdb -U postgres restored && pg_restore -U postgres -d restored --clean --if-exists /restore.dump'
docker exec "$container_name" psql -U postgres -d restored -Atqc 'SELECT version_num FROM alembic_version' | grep -E '^[0-9]{8}_[0-9]{4}$' >/dev/null
printf '%s\n' "PREPROD_RESTORE_VERIFIED"

