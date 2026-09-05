[CmdletBinding()]
param(
    [ValidateSet('auto', 'windows', 'wsl')]
    [string]$DockerMode = 'auto',
    [string]$WslDistribution = '',
    [int]$TestPostgresPort = 55432,
    [int]$TestRedisPort = 56379,
    [int]$TestMailpitSmtpPort = 51026,
    [int]$TestMailpitApiPort = 58026
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
# Vite et Vitest utilisent les chemins comme identifiants de modules. Sous Windows,
# une casse différente (par exemple "onedrive" au lieu de "OneDrive") peut donc
# charger deux instances de Vitest et désolidariser les matchers jest-dom de expect.
# realpathSync.native restitue la casse réellement enregistrée par le système de fichiers.
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if ($nodeCommand) {
    $canonicalWorkspace = & $nodeCommand.Source -e "console.log(require('fs').realpathSync.native(process.argv[1]))" $workspace
    if ($LASTEXITCODE -eq 0 -and $canonicalWorkspace) {
        $workspace = $canonicalWorkspace.Trim()
    }
}
$composeFile = Join-Path $workspace 'compose.test.yaml'
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$client = Join-Path $workspace 'client'
$testResults = Join-Path $workspace 'test-results'
$pytestTemp = Join-Path $testResults 'pytest-quality-tmp'
$qualityRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("marketteo-quality-{0}" -f ([guid]::NewGuid().ToString('N')))
$qualityClient = Join-Path $qualityRoot 'client'
$qualityNpmCache = Join-Path $qualityRoot 'npm-cache'
$vitestReport = Join-Path $testResults 'vitest.xml'
$projectName = 'prospect-crm-quality'
# Phase 3.1 ajoute la migration CSV et déplace la tête de référence.
$expectedAlembicRevision = '20260904_0015'
$script:resolvedDockerMode = $null
$script:wslWorkspace = $null
$script:wslDistribution = $null

function Invoke-QualityStep {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n[$Name]" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Le contrôle '$Name' a échoué avec le code $LASTEXITCODE."
    }
}

function Convert-ToWslPath {
    param([string]$Path)

    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $drive = $resolvedPath.Substring(0, 1).ToLowerInvariant()
    $pathWithoutDrive = $resolvedPath.Substring(2).Replace('\', '/')
    return "/mnt/$drive$pathWithoutDrive"
}

function Invoke-DockerCli {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    if ($script:resolvedDockerMode -eq 'wsl') {
        & wsl.exe -d $script:wslDistribution --cd $script:wslWorkspace env `
            "TEST_POSTGRES_PORT=$TestPostgresPort" `
            "TEST_REDIS_PORT=$TestRedisPort" `
            "TEST_MAILPIT_SMTP_PORT=$TestMailpitSmtpPort" `
            "TEST_MAILPIT_API_PORT=$TestMailpitApiPort" `
            docker @Arguments
        return
    }

    & docker @Arguments
}

function Get-ComposeFileArgument {
    if ($script:resolvedDockerMode -eq 'wsl') {
        return 'compose.test.yaml'
    }

    return $composeFile
}

function Initialize-QualityClient {
    New-Item -ItemType Directory -Path $qualityClient -Force -ErrorAction Stop | Out-Null
    Get-ChildItem -LiteralPath $client -Force |
        Where-Object { $_.Name -notin @('node_modules', 'dist') } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $qualityClient -Recurse -Force -ErrorAction Stop
        }
}

function Remove-QualityClient {
    if (-not (Test-Path -LiteralPath $qualityRoot)) {
        return
    }

    $temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
    $resolvedQualityRoot = [System.IO.Path]::GetFullPath($qualityRoot)
    $qualityRootParent = [System.IO.Path]::GetDirectoryName($resolvedQualityRoot)
    $qualityRootName = [System.IO.Path]::GetFileName($resolvedQualityRoot)
    if ($qualityRootParent -ne $temporaryRoot -or -not $qualityRootName.StartsWith('marketteo-quality-')) {
        throw "Nettoyage refusé pour le répertoire frontend temporaire inattendu : $resolvedQualityRoot"
    }

    Remove-Item -LiteralPath $resolvedQualityRoot -Recurse -Force -ErrorAction Stop
}

function Initialize-DockerCli {
    if ($DockerMode -eq 'windows') {
        $script:resolvedDockerMode = 'windows'
        return
    }

    if ($DockerMode -eq 'wsl') {
        $script:resolvedDockerMode = 'wsl'
        $script:wslWorkspace = Convert-ToWslPath $workspace
        $script:wslDistribution = Resolve-WslDistribution
        return
    }

    & docker version --format '{{.Server.Version}}' *> $null
    if ($LASTEXITCODE -eq 0) {
        $script:resolvedDockerMode = 'windows'
        return
    }

    $script:wslWorkspace = Convert-ToWslPath $workspace
    foreach ($distribution in Get-CandidateWslDistributions) {
        & wsl.exe -d $distribution --cd $script:wslWorkspace docker version --format '{{.Server.Version}}' *> $null
        if ($LASTEXITCODE -eq 0) {
            $script:resolvedDockerMode = 'wsl'
            $script:wslDistribution = $distribution
            return
        }
    }

    throw 'Docker est introuvable côté Windows et côté WSL.'
}

function Get-CandidateWslDistributions {
    if ($WslDistribution) {
        return @($WslDistribution)
    }

    $distributions = & wsl.exe --list --quiet
    if ($LASTEXITCODE -ne 0) {
        return @()
    }

    return @(
        $distributions |
            ForEach-Object { ($_ -replace "`0", '').Trim() } |
            Where-Object { $_ -and ($_ -notlike 'docker-desktop*') }
    )
}

function Resolve-WslDistribution {
    foreach ($distribution in Get-CandidateWslDistributions) {
        & wsl.exe -d $distribution --cd $script:wslWorkspace docker version --format '{{.Server.Version}}' *> $null
        if ($LASTEXITCODE -eq 0) {
            return $distribution
        }
    }

    throw "Aucune distribution WSL utilisable avec Docker n'a été trouvée. Précisez -WslDistribution avec une distribution Linux valide."
}

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Environnement Python .venv introuvable.'
}
New-Item -ItemType Directory -Force -Path $testResults | Out-Null

$env:TEST_POSTGRES_PORT = [string]$TestPostgresPort
$env:TEST_REDIS_PORT = [string]$TestRedisPort
$env:TEST_MAILPIT_SMTP_PORT = [string]$TestMailpitSmtpPort
$env:TEST_MAILPIT_API_PORT = [string]$TestMailpitApiPort
$env:TEST_DATABASE_URL = "postgresql+asyncpg://prospect_app:prospect-app-test-only@127.0.0.1:$TestPostgresPort/prospect_test"
$env:TEST_MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect_test:prospect-test-only@127.0.0.1:$TestPostgresPort/prospect_test"
$env:TEST_REDIS_URL = "redis://127.0.0.1:$TestRedisPort/0"
$env:TEST_MAILPIT_API_URL = "http://127.0.0.1:$TestMailpitApiPort"
$env:REQUIRE_INFRASTRUCTURE_TESTS = 'true'
$env:MIGRATION_DATABASE_URL = $env:TEST_MIGRATION_DATABASE_URL

try {
    Invoke-QualityStep 'Docker disponible' {
        Initialize-DockerCli
        Write-Host "Mode Docker retenu : $script:resolvedDockerMode"
        if ($script:resolvedDockerMode -eq 'wsl') {
            Write-Host "Répertoire WSL : $script:wslWorkspace"
            Write-Host "Distribution WSL : $script:wslDistribution"
        }
        Invoke-DockerCli version
    }
    Invoke-QualityStep 'Nettoyage de la composition de test' {
        Invoke-DockerCli -Arguments @('compose', '-p', $projectName, '-f', (Get-ComposeFileArgument), 'down', '--volumes', '--remove-orphans')
    }
    Invoke-QualityStep 'Dépendances réelles' {
        Invoke-DockerCli -Arguments @('compose', '-p', $projectName, '-f', (Get-ComposeFileArgument), 'up', '-d', '--wait')
    }
    Invoke-QualityStep 'Rôle PostgreSQL applicatif' {
        Invoke-DockerCli -Arguments @('compose', '-p', $projectName, '-f', (Get-ComposeFileArgument), 'run', '--rm', 'database-role-provisioner')
    }
    Invoke-QualityStep 'Alembic upgrade' { & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') upgrade head }
    Invoke-QualityStep 'Alembic reconstruction' {
        & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') downgrade 20260723_0002
        if ($LASTEXITCODE -ne 0) { throw 'Le downgrade Alembic de test a échoué.' }
        & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') upgrade head
    }
    Invoke-QualityStep 'Alembic current' {
        $currentReport = Join-Path $testResults 'alembic-current.txt'
        $currentOutput = & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') current
        if ($LASTEXITCODE -ne 0) { throw 'La lecture de la révision Alembic courante a échoué.' }
        $currentOutput | ForEach-Object { Write-Host $_ }
        Set-Content -LiteralPath $currentReport -Value $currentOutput -Encoding utf8
        & $python (Join-Path $workspace 'scripts\quality_gate.py') alembic-current $currentReport $expectedAlembicRevision
    }
    Invoke-QualityStep 'Alembic check' { & $python -m alembic -c (Join-Path $workspace 'backend\alembic.ini') check }
    Invoke-QualityStep 'Ruff' { & $python -m ruff check (Join-Path $workspace 'backend\app') (Join-Path $workspace 'tests') (Join-Path $workspace 'scripts\quality_gate.py') }
    Invoke-QualityStep 'Format Ruff' { & $python -m ruff format --check (Join-Path $workspace 'backend\app') (Join-Path $workspace 'tests') (Join-Path $workspace 'scripts\quality_gate.py') }
    Invoke-QualityStep 'mypy' { Push-Location $workspace; try { & $python -m mypy } finally { Pop-Location } }
    Invoke-QualityStep 'pytest réel' {
        Push-Location $workspace
        try {
            & $python -m pytest -p no:cacheprovider "--basetemp=$pytestTemp" --junitxml=test-results/pytest-quality.xml
        }
        finally {
            Pop-Location
        }
    }
    Invoke-QualityStep 'Zéro skip backend' { & $python (Join-Path $workspace 'scripts\quality_gate.py') junit-no-skips (Join-Path $testResults 'pytest-quality.xml') }
    Invoke-QualityStep 'Préparation frontend isolée' {
        Initialize-QualityClient
        $global:LASTEXITCODE = 0
    }
    Invoke-QualityStep 'npm ci' {
        Push-Location $qualityClient
        try { npm.cmd ci --cache $qualityNpmCache }
        finally { Pop-Location }
    }
    Invoke-QualityStep 'Audit npm' {
        Push-Location $qualityClient
        try { npm.cmd audit --audit-level=high --cache $qualityNpmCache }
        finally { Pop-Location }
    }
    Invoke-QualityStep 'ESLint' { Push-Location $qualityClient; try { npm.cmd run lint } finally { Pop-Location } }
    Invoke-QualityStep 'Vitest avec axe' {
        Push-Location $qualityClient
        try {
            & (Join-Path $qualityClient 'node_modules\.bin\vitest.cmd') run --reporter=default --reporter=junit "--outputFile.junit=$vitestReport"
        }
        finally {
            Pop-Location
        }
    }
    Invoke-QualityStep 'Zéro skip frontend' { & $python (Join-Path $workspace 'scripts\quality_gate.py') junit-no-skips $vitestReport }
    Invoke-QualityStep 'Build Vite' { Push-Location $qualityClient; try { npm.cmd run build } finally { Pop-Location } }
    Invoke-QualityStep 'Sources navigateur' { & $python (Join-Path $workspace 'scripts\quality_gate.py') browser-sources (Join-Path $client 'src') }
    Invoke-QualityStep 'Artefact Vite' { & $python (Join-Path $workspace 'scripts\quality_gate.py') artifact (Join-Path $qualityClient 'dist') }
    Invoke-QualityStep 'Diff Git' { Push-Location $workspace; try { git --no-pager diff --check } finally { Pop-Location } }
    $summary = @(
        '# Rapport du verrou qualité local 3.2'
        ''
        "- Date UTC : $([DateTime]::UtcNow.ToString('u'))"
        "- Mode Docker : $script:resolvedDockerMode"
        "- Révision Alembic attendue : $expectedAlembicRevision"
        '- Verdict automatisé : VERT'
        '- Rapports : `pytest-quality.xml`, `vitest.xml`, `alembic-current.txt`'
    )
    Set-Content -LiteralPath (Join-Path $testResults 'quality-summary.md') -Value $summary -Encoding utf8
    Write-Host "`nVerrou qualité local 3.2 : VERT" -ForegroundColor Green
}
finally {
    if ($script:resolvedDockerMode) {
        Invoke-DockerCli -Arguments @('compose', '-p', $projectName, '-f', (Get-ComposeFileArgument), 'down', '--volumes', '--remove-orphans')
    }
    try {
        Remove-QualityClient
    }
    catch {
        Write-Warning "Le répertoire frontend temporaire n'a pas pu être supprimé : $($_.Exception.Message)"
    }
}
