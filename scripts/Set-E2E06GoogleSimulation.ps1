[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04',

    [ValidateSet('Enable', 'Disable')]
    [string]$Mode = 'Enable'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$workspaceWsl = (& wsl -d $WslDistribution -- wslpath -a $workspace).Trim()
if ($LASTEXITCODE -ne 0 -or -not $workspaceWsl) {
    throw "Impossible de résoudre le répertoire WSL pour $workspace."
}
if ($workspaceWsl -match "[\r\n']") {
    throw 'Le chemin de travail WSL contient un caractère non pris en charge.'
}

function Invoke-WslBash {
    param([Parameter(Mandatory)][string]$Script)

    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Script))
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& wsl -d $WslDistribution -- bash -lc "printf '%s' $encoded | base64 -d | bash" 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "La commande WSL E2E-06 a échoué (code $exitCode)."
    }
    $output | ForEach-Object { Write-Host $_ }
    return $output
}

$enabled = if ($Mode -eq 'Enable') { 'true' } else { 'false' }
Invoke-WslBash -Script @"
set -euo pipefail
cd '$workspaceWsl'
if [ '$enabled' = 'true' ]; then
  docker compose --profile runtime build --no-cache api
fi
GOOGLE_PLACES_SIMULATOR_ENABLED=$enabled docker compose --profile runtime up -d --force-recreate api
"@ | Out-Null

$health = Invoke-RestMethod 'http://localhost:8000/api/health'
if ($Mode -eq 'Enable' -and -not $health.google_api_key_configured) {
    throw 'Le simulateur Google E2E-06 n est pas actif apres le redemarrage de l API.'
}
if ($Mode -eq 'Enable' -and $health.google_places_mode -ne 'simulated') {
    throw 'http://localhost:8000 ne repond pas avec l API Docker simulee. Fermez l API locale concurrente et ouvrez http://localhost:8000 dans le navigateur.'
}

if ($Mode -eq 'Enable') {
    $simulationState = Invoke-WslBash -Script @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime exec -T api python - <<'PY'
from backend.app.bootstrap import build_container
from backend.app.config import Settings

container = build_container(Settings.from_env())
print(
    "SIMULATOR_STATE="
    + type(container.search_google_places._places).__name__
    + "|"
    + str(container.search_google_places._issue_map_snapshot)
)
PY
"@ | Where-Object { $_ -match '^SIMULATOR_STATE=' } | Select-Object -Last 1
    if ($simulationState -ne 'SIMULATOR_STATE=SimulatedGooglePlacesGateway|False') {
        throw 'Le conteneur API ne confirme pas le fournisseur Google simule ou le blocage des jetons de carte.'
    }

    $sensitiveColumnCount = Invoke-WslBash -Script @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -Atqc "
  SELECT count(*)
  FROM information_schema.columns
  WHERE table_name IN ('usage_operation_events', 'usage_daily_counters')
    AND (
      column_name ILIKE '%query%'
      OR column_name ILIKE '%response%'
      OR column_name IN ('latitude', 'longitude')
      OR column_name ILIKE '%cost%'
    );
"
"@ | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1
    if ($sensitiveColumnCount -ne '0') {
        throw 'Le schema durable de l usage contient un champ interdit pour E2E-06.'
    }
}
if ($Mode -eq 'Enable') {
    Write-Host 'E2E-06 est prêt : faux fournisseur confirmé, jetons de carte bloqués et schéma durable sans champ Google sensible.'
}
else {
    Write-Host 'Le fournisseur Google simulé est désactivé.'
}
