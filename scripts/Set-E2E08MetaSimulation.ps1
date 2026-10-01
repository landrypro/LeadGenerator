[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04'
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

function Set-LocalEnvironmentValue {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Value
    )

    $environmentPath = Join-Path $workspace '.env'
    $lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $environmentPath) {
        foreach ($line in [System.IO.File]::ReadAllLines($environmentPath)) {
            $lines.Add($line)
        }
    }
    $prefix = "$Name="
    $updated = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index].StartsWith($prefix, [System.StringComparison]::Ordinal)) {
            $lines[$index] = "$prefix$Value"
            $updated = $true
        }
    }
    if (-not $updated) {
        $lines.Add("$prefix$Value")
    }
    [System.IO.File]::WriteAllLines($environmentPath, $lines)
}

$simulationValues = [ordered]@{
    META_LEAD_ADS_ENABLED = 'true'
    META_LEAD_ADS_SIMULATOR_ENABLED = 'true'
    META_WEBHOOK_VERIFY_TOKEN = 'e2e08-verify-token-local-20260928'
    META_WEBHOOK_APP_SECRET = 'e2e08-app-secret-local-20260928-xxxxxxxx'
    META_REFERENCE_HMAC_KEY = 'e2e08-reference-hmac-local-20260928-xxxxxxxx'
    META_LEAD_REFERENCE_ENCRYPTION_KEY = 'e2e08-reference-encryption-local-20260928'
    META_GRAPH_ACCESS_TOKEN = 'e2e08-graph-token-local-20260928-xxxxxxxx'
    META_GRAPH_API_BASE_URL = 'https://graph.facebook.com'
    CORS_ALLOWED_ORIGINS = 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173'
}
foreach ($entry in $simulationValues.GetEnumerator()) {
    Set-LocalEnvironmentValue -Name $entry.Key -Value $entry.Value
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
    $output | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) {
        throw "La préparation WSL E2E-08 a échoué (code $exitCode)."
    }
}

Invoke-WslBash -Script @"
set -euo pipefail
cd '$workspaceWsl'

# Valeurs synthétiques locales : elles permettent de vérifier la signature et
# le chiffrement sans utiliser un secret Meta réel ni appeler Graph API.
export META_LEAD_ADS_ENABLED=true
export META_LEAD_ADS_SIMULATOR_ENABLED=true
export META_WEBHOOK_VERIFY_TOKEN='e2e08-verify-token-local-20260928'
export META_WEBHOOK_APP_SECRET='e2e08-app-secret-local-20260928-xxxxxxxx'
export META_REFERENCE_HMAC_KEY='e2e08-reference-hmac-local-20260928-xxxxxxxx'
export META_LEAD_REFERENCE_ENCRYPTION_KEY='e2e08-reference-encryption-local-20260928'
export META_GRAPH_ACCESS_TOKEN='e2e08-graph-token-local-20260928-xxxxxxxx'
export META_GRAPH_API_BASE_URL='https://graph.facebook.com'
export CORS_ALLOWED_ORIGINS='http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173'

docker compose --profile runtime build api worker
docker compose --profile runtime up -d --force-recreate api worker
docker compose --profile runtime exec -T api python - <<'PY'
from backend.app.config import Settings

settings = Settings.from_env()
assert settings.meta_lead_ads_enabled is True
assert settings.meta_lead_ads_simulator_enabled is True
assert len(settings.meta_reference_hmac_key.encode()) >= 32
assert len(settings.meta_lead_reference_encryption_key.encode()) >= 32
assert 'http://localhost:8000' in settings.cors_allowed_origins
assert 'http://localhost:5173' in settings.cors_allowed_origins
print('E2E08_META_SIMULATION=READY enabled=true simulator=true secrets=synthetic')
PY
"@

Write-Host 'E2E-08 est prêt. Recharger la page Connexions et créer le brouillon Meta.' -ForegroundColor Green
