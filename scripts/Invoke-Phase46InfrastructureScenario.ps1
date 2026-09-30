[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^E2E-[0-9]{2}$')]
    [string]$Scenario,

    [Parameter(Mandatory)]
    [string]$Description,

    [Parameter(Mandatory)]
    [string[]]$RequiredTestClasses,

    [string]$WslDistribution = 'Ubuntu-24.04'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$qualityGate = Join-Path $PSScriptRoot 'Test-QualityGateLocal.ps1'
$report = Join-Path $workspace 'test-results\pytest-quality.xml'

if (-not (Test-Path -LiteralPath $qualityGate)) {
    throw 'Le verrou qualité local est introuvable.'
}

Write-Host "$Scenario — $Description" -ForegroundColor Cyan

# Les ports diffèrent du runtime local (55432/6379) : le verrou crée sa base
# PostgreSQL temporaire, ses rôles applicatifs et Redis sans interrompre l'application.
& $qualityGate `
    -DockerMode wsl `
    -WslDistribution $WslDistribution `
    -TestPostgresPort 56432 `
    -TestRedisPort 56380 `
    -TestMailpitSmtpPort 51027 `
    -TestMailpitApiPort 58027
if ($LASTEXITCODE -ne 0) {
    throw "$Scenario a échoué pendant le verrou qualité avec l'infrastructure isolée."
}
if (-not (Test-Path -LiteralPath $report)) {
    throw 'Rapport pytest du verrou qualité introuvable.'
}

[xml]$junit = Get-Content -LiteralPath $report -Raw
$selectedCases = @()
foreach ($testClass in $RequiredTestClasses) {
    $classCases = @($junit.SelectNodes("//testcase[contains(@classname, '$testClass') ]"))
    if ($classCases.Count -lt 1) {
        throw "Aucun test d'infrastructure trouvé pour $testClass."
    }
    $selectedCases += $classCases
}

$invalidCases = @($selectedCases | Where-Object { $_.failure -or $_.error -or $_.skipped })
if ($invalidCases.Count -ne 0) {
    throw "$Scenario contient $($invalidCases.Count) test(s) requis ignoré(s) ou en échec."
}

Write-Host "$Scenario`_SCRIPT=PASS tests=$($selectedCases.Count) rapport=$report" -ForegroundColor Green
