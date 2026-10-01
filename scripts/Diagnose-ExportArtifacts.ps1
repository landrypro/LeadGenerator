[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04',

    [ValidateRange(1, 25)]
    [int]$Limit = 10
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

function Invoke-WslCommand {
    param([Parameter(Mandatory)][string]$Command)

    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& wsl -d $WslDistribution --cd $workspaceWsl bash -lc $Command 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedPreference
    }
    if ($exitCode -ne 0) {
        throw "Commande WSL échouée (code $exitCode) : $($output -join [Environment]::NewLine)"
    }
    return $output
}

function Get-ArtifactFileStatus {
    param(
        [Parameter(Mandatory)][string]$Service,
        [Parameter(Mandatory)][string]$FileRef,
        [Parameter(Mandatory)][string]$ExpectedBytes,
        [Parameter(Mandatory)][string]$ExpectedSha256
    )

    $path = "/app/.runtime/imports/exports/$FileRef.csv"
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& wsl -d $WslDistribution --cd $workspaceWsl docker compose --profile runtime exec -T $Service stat -c '%s' $path 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedPreference
    }

    if ($exitCode -ne 0) {
        $text = $output -join [Environment]::NewLine
        if ($text -match 'No such file|cannot stat') {
            return [pscustomobject]@{ Present = $false; ActualBytes = $null; MatchesDatabase = $false; MatchesSha256 = $false }
        }
        throw "Lecture du fichier d’export dans $Service échouée (code $exitCode) : $text"
    }
    $actual = ([string]($output | Select-Object -Last 1)).Trim()
    if ($actual -notmatch '^\d+$') {
        throw "Taille de fichier inattendue dans $Service : $actual"
    }
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $hashOutput = @(& wsl -d $WslDistribution --cd $workspaceWsl docker compose --profile runtime exec -T $Service sha256sum $path 2>&1)
        $hashExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedPreference
    }
    if ($hashExitCode -ne 0) {
        throw "Calcul SHA-256 dans $Service échoué (code $hashExitCode) : $($hashOutput -join [Environment]::NewLine)"
    }
    $actualSha256 = (([string]($hashOutput | Select-Object -Last 1)).Trim() -split '\s+')[0]
    if ($actualSha256 -notmatch '^[0-9a-f]{64}$') {
        throw "Empreinte SHA-256 inattendue dans $Service : $actualSha256"
    }
    return [pscustomobject]@{
        Present = $true
        ActualBytes = [Int64]$actual
        MatchesDatabase = ($actual -eq $ExpectedBytes)
        MatchesSha256 = ($actualSha256 -eq $ExpectedSha256)
    }
}

foreach ($service in 'api', 'worker', 'postgresql') {
    $containerOutput = @(Invoke-WslCommand "docker compose --profile runtime ps -q $service")
    $containerId = if ($containerOutput.Count) { ([string]($containerOutput | Select-Object -Last 1)).Trim() } else { '' }
    if (-not $containerId) {
        Write-Host "EXPORT_DIAGNOSTIC=UNAVAILABLE service=$service" -ForegroundColor Yellow
        Write-Host 'Démarrer les services avec : docker compose --profile runtime up -d --build api worker'
        exit 0
    }
}

$sql = @'
SELECT r.id,
       r.status,
       COALESCE(a.file_ref, ''),
       COALESCE(a.byte_size::text, ''),
       COALESCE(a.sha256, ''),
       COALESCE(to_char(a.expires_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS UTC'), ''),
       COALESCE(to_char(a.deleted_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS UTC'), ''),
       to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS UTC'),
       CASE
         WHEN a.export_id IS NULL THEN 'artifact_absent'
         WHEN a.deleted_at IS NOT NULL THEN 'artifact_deleted'
         WHEN a.expires_at <= clock_timestamp() THEN 'artifact_expired'
         ELSE 'artifact_active'
       END
FROM export_requests r
LEFT JOIN export_artifacts a ON a.export_id = r.id
ORDER BY r.created_at DESC, r.id DESC
LIMIT __LIMIT__;
'@.Replace('__LIMIT__', $Limit)
$encodedSql = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sql))
$rows = @(Invoke-WslCommand "printf '%s' $encodedSql | base64 -d | docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -At -F '|'" |
    Where-Object { $_ -match '^[0-9a-fA-F-]{36}\|' })

if ($rows.Count -eq 0) {
    Write-Host 'EXPORT_DIAGNOSTIC=NO_EXPORT_REQUEST' -ForegroundColor Yellow
    exit 0
}

Write-Host 'EXPORT_DIAGNOSTIC=READY' -ForegroundColor Green
foreach ($line in $rows) {
    $columns = $line.Trim().Split('|')
    if ($columns.Count -ne 9) {
        throw "Format de diagnostic inattendu : $line"
    }
    $exportId, $status, $fileRef, $byteSize, $sha256, $expiresAt, $deletedAt, $databaseClock, $artifactState = $columns
    $expiry = if ($expiresAt) { $expiresAt } else { 'none' }
    $deleted = if ($deletedAt) { $deletedAt } else { 'none' }
    $size = if ($byteSize) { $byteSize } else { 'none' }
    Write-Host "EXPORT_ARTIFACT id=$exportId request_status=$status artifact_state=$artifactState database_clock=$databaseClock expires_at=$expiry deleted_at=$deleted expected_bytes=$size"
    if ($fileRef -notmatch '^[0-9a-f]{48}$') {
        continue
    }
    foreach ($service in 'api', 'worker') {
        $file = Get-ArtifactFileStatus -Service $service -FileRef $fileRef -ExpectedBytes $byteSize -ExpectedSha256 $sha256
        if (-not $file.Present) {
            Write-Host "EXPORT_FILE service=$service present=false"
        }
        else {
            $matching = $file.MatchesDatabase.ToString().ToLowerInvariant()
            $matchingSha = $file.MatchesSha256.ToString().ToLowerInvariant()
            Write-Host "EXPORT_FILE service=$service present=true actual_bytes=$($file.ActualBytes) matches_database=$matching matches_sha256=$matchingSha"
        }
    }
}

Write-Host 'Lecture seule : aucune donnée, fichier ou demande d export n a été modifié.' -ForegroundColor DarkGray
