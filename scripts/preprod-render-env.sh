#!/usr/bin/env sh
# Produit un fichier runtime depuis des SecureString Parameter Store, sans les écrire dans les journaux.
set -eu

template=${1:-.env.preprod.example}
output=${2:-.env.preprod}
test -f "$template"

prefix=$(awk -F= '/^PREPROD_PARAMETER_PREFIX=/{print substr($0, index($0, "=") + 1)}' "$template")
test -n "$prefix" || { echo "PREPROD_PARAMETER_PREFIX est obligatoire." >&2; exit 1; }
case "$prefix" in
  /*) ;;
  *) echo "PREPROD_PARAMETER_PREFIX doit commencer par /." >&2; exit 1 ;;
esac

secret_names="METRICS_BEARER_TOKEN POSTGRES_PASSWORD POSTGRES_APP_PASSWORD POSTGRES_WORKER_PASSWORD DATABASE_URL MIGRATION_DATABASE_URL WORKER_DATABASE_URL JOB_IDEMPOTENCY_HMAC_KEY RATE_LIMIT_HMAC_KEY GOOGLE_MAPS_API_KEY GOOGLE_MAPS_STATIC_API_KEY"
output_dir=$(dirname "$output")
mkdir -p "$output_dir"
umask 077
temporary="$output_dir/.preprod-env-$$"
trap 'rm -f "$temporary"' EXIT HUP INT TERM

secret_value() {
  parameter_name=$1
  value=$(aws ssm get-parameter --name "$prefix/$parameter_name" --with-decryption --query 'Parameter.Value' --output text)
  compact=$(printf '%s' "$value" | tr -d '\r\n')
  test "$value" = "$compact" || { echo "Le paramètre $parameter_name contient un retour à la ligne interdit." >&2; exit 1; }
  printf '%s' "$value"
}

is_secret_name() {
  for candidate in $secret_names; do
    test "$candidate" = "$1" && return 0
  done
  return 1
}

while IFS= read -r line || test -n "$line"; do
  case "$line" in
    ''|'#'*) printf '%s\n' "$line" >> "$temporary" ;;
    *=*)
      name=${line%%=*}
      if is_secret_name "$name"; then
        printf '%s=' "$name" >> "$temporary"
        secret_value "$name" >> "$temporary"
        printf '\n' >> "$temporary"
      else
        printf '%s\n' "$line" >> "$temporary"
      fi
      ;;
    *) echo "$template contient une ligne invalide : $line" >&2; exit 1 ;;
  esac
done < "$template"

mv "$temporary" "$output"
trap - EXIT HUP INT TERM
printf '%s\n' "PREPROD_ENV_RENDERED"
