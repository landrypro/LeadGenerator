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

& "$PSScriptRoot\Invoke-Phase46PytestScenario.ps1" `
    -Scenario 'E2E-12' `
    -Description 'Prévol de rétention, archivage en cascade et contrôle des droits' `
    -Tests @(
        'tests/test_retention_use_cases.py',
        'tests/test_retention_api.py'
    )

$purgeSql = "SELECT count(*) FROM prospects WHERE archived_at IS NULL AND (internal_alias LIKE 'P4-ALPHA%' OR internal_alias LIKE 'QA-P46-%');"
$purgeSqlEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($purgeSql))
$purgeCommand = "printf '%s' $purgeSqlEncoded | base64 -d | docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -Atq"
$candidateCount = @(& wsl -d $WslDistribution --cd $workspaceWsl bash -lc $purgeCommand 2>&1) |
    Where-Object { $_ -match '^\d+$' } |
    Select-Object -Last 1
if (-not $candidateCount) {
    throw 'Le comptage de prévol E2E-12 est indisponible.'
}

Write-Host "E2E12_PURGE=READY candidates=$candidateCount" -ForegroundColor Yellow
Write-Host 'Aucune donnée n est supprimée par ce prévol. Exécuter la purge finale seulement après validation explicite de la liste des candidats.'
