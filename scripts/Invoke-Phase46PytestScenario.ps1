[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^E2E-[0-9]{2}$')]
    [string]$Scenario,

    [Parameter(Mandatory)]
    [string[]]$Tests,

    [Parameter(Mandatory)]
    [string]$Description
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$reportDirectory = Join-Path $workspace 'test-results\phase-4-6\scripted'
$report = Join-Path $reportDirectory ("{0}.xml" -f $Scenario.ToLowerInvariant())

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Environnement Python .venv introuvable.'
}
foreach ($test in $Tests) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspace $test))) {
        throw "Test introuvable pour $Scenario : $test"
    }
}

New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
$pytestBaseTemp = Join-Path $reportDirectory ("pytest-tmp-{0}-{1}" -f $Scenario.ToLowerInvariant(), [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $pytestBaseTemp | Out-Null
Write-Host "$Scenario — $Description" -ForegroundColor Cyan

Push-Location $workspace
try {
    # tmp_path ne doit pas dépendre d'un ancien répertoire pytest global dont
    # les ACL Windows peuvent appartenir à un autre compte ou à Docker Desktop.
    & $python -m pytest -q "--basetemp=$pytestBaseTemp" @Tests "--junitxml=$report"
    if ($LASTEXITCODE -ne 0) {
        throw "$Scenario a échoué. Consultez $report."
    }
}
finally {
    Pop-Location
}

[xml]$junit = Get-Content -LiteralPath $report -Raw
$suites = @($junit.SelectNodes('//testsuite'))
$testsRun = 0
$failures = 0
$errors = 0
$skipped = 0
foreach ($suite in $suites) {
    foreach ($counter in @('tests', 'failures', 'errors', 'skipped')) {
        $rawValue = $suite.GetAttribute($counter)
        $value = if ([string]::IsNullOrWhiteSpace($rawValue)) { 0 } else { [int]$rawValue }
        switch ($counter) {
            'tests' { $testsRun += $value }
            'failures' { $failures += $value }
            'errors' { $errors += $value }
            'skipped' { $skipped += $value }
        }
    }
}
if ($testsRun -lt 1 -or $failures -ne 0 -or $errors -ne 0 -or $skipped -ne 0) {
    throw "$Scenario ne fournit pas une preuve complète : tests=$testsRun, failures=$failures, errors=$errors, skipped=$skipped."
}

Write-Host "$Scenario`_SCRIPT=PASS tests=$testsRun rapport=$report" -ForegroundColor Green
