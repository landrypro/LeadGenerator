#!/bin/sh

set -eu

if [ "${POSTGRES_APP_USER:-}" != "prospect_app" ]; then
    echo "POSTGRES_APP_USER doit valoir prospect_app (contrat des migrations)." >&2
    exit 1
fi

if [ -z "${POSTGRES_APP_PASSWORD:-}" ]; then
    echo "POSTGRES_APP_PASSWORD est obligatoire." >&2
    exit 1
fi

export PGPASSWORD="${POSTGRES_PASSWORD}"

psql \
    --host postgresql \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" \
    --set ON_ERROR_STOP=1 \
    --set app_user="${POSTGRES_APP_USER}" \
    --set app_password="${POSTGRES_APP_PASSWORD}" \
    --set owner_user="${POSTGRES_USER}" <<'SQL'
SELECT format(
    'CREATE ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD %L',
    :'app_user',
    :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD %L',
    :'app_user',
    :'app_password'
) \gexec

SELECT 'CREATE ROLE prospect_rls_definer WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prospect_rls_definer') \gexec

ALTER ROLE prospect_rls_definer
    WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;

SELECT format('GRANT prospect_rls_definer TO %I', :'owner_user') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user') \gexec
SQL
