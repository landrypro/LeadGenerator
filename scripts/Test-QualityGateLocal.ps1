[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $workspace 'compose.test.yaml'
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$client = Join-Path $workspace 'client'
$testResults = Join-Path $workspace 'test-results'
$projectName = 'prospect-crm-quality'
$expectedAlembicRevision = '20260813_0008'

function Invoke-QualityStep {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n[$Name]" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Le contrôle '$Name' a échoué avec le code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Environnement Python .venv introuvable.'
}
New-Item -ItemType Directory -Force -Path $testResults | Out-Null

$env:TEST_DATABASE_URL = 'postgresql+asyncpg://prospect_app:prospect-app-test-only@127.0.0.1:55432/prospect_test'
$env:TEST_MIGRATION_DATABASE_URL = 'postgresql+asyncpg://prospect_test:prospect-test-only@127.0.0.1:55432/prospect_test'
$env:TEST_REDIS_URL = 'redis://127.0.0.1:56379/0'
$env:TEST_MAILPIT_API_URL = 'http://127.0.0.1:58025'
$env:TEST_MAILPIT_SMTP_PORT = '51025'
$env:REQUIRE_INFRASTRUCTURE_TESTS = 'true'
$env:MIGRATION_DATABASE_URL = $env:TEST_MIGRATION_DATABASE_URL

try {
    Invoke-QualityStep 'Docker disponible' { docker version }
    Invoke-QualityStep 'Nettoyage de la composition de test' { docker compose -p $projectName -f $composeFile down --volumes --remove-orphans }
    Invoke-QualityStep 'Dépendances réelles' { docker compose -p $projectName -f $composeFile up -d --wait }
    Invoke-QualityStep 'Rôle PostgreSQL applicatif' { docker compose -p $projectName -f $composeFile run --rm database-role-provisioner }
    Invoke-QualityStep 'Alembic upgrade' { & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') upgrade head }
    Invoke-QualityStep 'Alembic reconstruction' {
        & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') downgrade 20260723_0002
        if ($LASTEXITCODE -ne 0) { throw 'Le downgrade Alembic de test a échoué.' }
        & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') upgrade head
    }
    Invoke-QualityStep 'Alembic current' {
        $currentReport = Join-Path $testResults 'alembic-current.txt'
        & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') current | Tee-Object -FilePath $currentReport
        if ($LASTEXITCODE -ne 0) { throw 'La lecture de la révision Alembic courante a échoué.' }
        & $python (Join-Path $workspace 'scripts\quality_gate.py') alembic-current $currentReport $expectedAlembicRevision
    }
    Invoke-QualityStep 'Alembic check' { & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') check }
    Invoke-QualityStep 'Ruff' { & $python -m ruff check (Join-Path $workspace 'backend\app') (Join-Path $workspace 'tests') (Join-Path $workspace 'scripts\quality_gate.py') }
    Invoke-QualityStep 'Format Ruff' { & $python -m ruff format --check (Join-Path $workspace 'backend\app') (Join-Path $workspace 'tests') (Join-Path $workspace 'scripts\quality_gate.py') }
    Invoke-QualityStep 'mypy' { Push-Location $workspace; try { & $python -m mypy } finally { Pop-Location } }
    Invoke-QualityStep 'pytest réel' { Push-Location $workspace; try { & $python -m pytest -p no:cacheprovider --junitxml=test-results/pytest-quality.xml } finally { Pop-Location } }
    Invoke-QualityStep 'Zéro skip backend' { & $python (Join-Path $workspace 'scripts\quality_gate.py') junit-no-skips (Join-Path $testResults 'pytest-quality.xml') }
    Invoke-QualityStep 'npm ci' { Push-Location $client; try { npm.cmd ci } finally { Pop-Location } }
    Invoke-QualityStep 'Audit npm' { Push-Location $client; try { npm.cmd audit --audit-level=high } finally { Pop-Location } }
    Invoke-QualityStep 'ESLint' { Push-Location $client; try { npm.cmd run lint } finally { Pop-Location } }
    Invoke-QualityStep 'Vitest avec axe' { Push-Location $client; try { npm.cmd run test:ci } finally { Pop-Location } }
    Invoke-QualityStep 'Zéro skip frontend' { & $python (Join-Path $workspace 'scripts\quality_gate.py') junit-no-skips (Join-Path $testResults 'vitest.xml') }
    Invoke-QualityStep 'Build Vite' { Push-Location $client; try { npm.cmd run build } finally { Pop-Location } }
    Invoke-QualityStep 'Sources navigateur' { & $python (Join-Path $workspace 'scripts\quality_gate.py') browser-sources (Join-Path $client 'src') }
    Invoke-QualityStep 'Artefact Vite' { & $python (Join-Path $workspace 'scripts\quality_gate.py') artifact (Join-Path $client 'dist') }
    Invoke-QualityStep 'Diff Git' { Push-Location $workspace; try { git diff --check } finally { Pop-Location } }
    Write-Host "`nVerrou qualité local 2.4.5 : VERT" -ForegroundColor Green
}
finally {
    docker compose -p $projectName -f $composeFile down --volumes --remove-orphans
}
