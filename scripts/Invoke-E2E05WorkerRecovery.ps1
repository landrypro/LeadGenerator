[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04',

    [ValidateRange(30, 900)]
    [int]$WatchSeconds = 900,

    [ValidateRange(91, 300)]
    [int]$LeaseWaitSeconds = 100
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
    param(
        [Parameter(Mandatory)]
        [string]$Script,

        [switch]$Quiet
    )

    # Chaque commande est encodée séparément. Envoyer le scénario complet dans
    # une seule ligne de commande Windows peut le tronquer vers 8 Ko.
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Script))
    # Docker Compose écrit sa progression sur stderr même lorsque la commande
    # réussit. Il faut donc différer ErrorActionPreference jusqu'au code de
    # sortie réel de bash, qui reste le critère de succès.
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
        throw "La commande WSL E2E-05 a échoué (code $exitCode)."
    }
    if (-not $Quiet) {
        $output | ForEach-Object { Write-Host $_ }
    }
    return $output
}

$unlockScript = @'
set -euo pipefail
cd '__WORKSPACE__'
database_container=$(docker compose --profile runtime ps -q postgresql)
if [ -n "$database_container" ]; then
  docker exec "$database_container" psql -U prospect -d prospect -Atqc "
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE application_name = 'e2e05_export_lock'
      AND pid <> pg_backend_pid();
  " >/dev/null
fi
'@.Replace('__WORKSPACE__', $workspaceWsl)

$lockHeld = $true
function Release-E2E05ExportLock {
    if (-not $script:lockHeld) {
        return
    }
    try {
        Invoke-WslBash -Quiet -Script $unlockScript | Out-Null
    }
    catch {
        Write-Warning "Impossible de libérer automatiquement le verrou E2E-05 : $($_.Exception.Message)"
    }
    finally {
        $script:lockHeld = $false
    }
}

try {
$prepareScript = @'
set -euo pipefail
cd '__WORKSPACE__'
docker compose --profile runtime stop worker || true
docker compose --profile runtime rm -f worker || true
docker compose --profile runtime up -d --build --scale worker=1 worker
database_container=$(docker compose --profile runtime ps -q postgresql)
test -n "$database_container"
docker exec "$database_container" psql -U prospect -d prospect -Atqc "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE application_name = 'e2e05_export_lock'
    AND pid <> pg_backend_pid();
" >/dev/null
docker exec -d -e PGAPPNAME=e2e05_export_lock "$database_container" sh -lc \
  'exec psql -v ON_ERROR_STOP=1 -U prospect -d prospect -c "BEGIN; LOCK TABLE prospects IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(600);" >/tmp/e2e05-export-lock.log 2>&1'
for _ in $(seq 1 100); do
  lock_ready=$(docker exec "$database_container" psql -U prospect -d prospect -Atqc "
    SELECT 1 FROM pg_stat_activity WHERE application_name = 'e2e05_export_lock' LIMIT 1;
  " | tr -d '\r\n')
  if [ "$lock_ready" = '1' ]; then
    docker exec "$database_container" psql -U prospect -d prospect -Atqc 'SELECT clock_timestamp()' | sed 's/^/STARTED_AT=/'
    exit 0
  fi
  sleep 0.05
done
echo 'Le verrou E2E-05 n est pas devenu actif.' >&2
exit 1
'@.Replace('__WORKSPACE__', $workspaceWsl)
$prepareOutput = Invoke-WslBash -Script $prepareScript
$startedAtLine = $prepareOutput | Where-Object { $_ -match '^STARTED_AT=' } | Select-Object -Last 1
if (-not $startedAtLine) {
    throw 'Le point de départ E2E-05 est introuvable dans PostgreSQL.'
}
$startedAt = $startedAtLine.ToString().Substring('STARTED_AT='.Length).Trim()
if (-not $startedAt) {
    throw 'Le point de départ E2E-05 est vide.'
}

Write-Host ''
Write-Host "E2E-05 est armé. Créez maintenant une seule nouvelle demande d'export dans le navigateur."
Write-Host "Le script attend jusqu'à $WatchSeconds secondes l'état running, puis interrompt le worker."

$watchDeadline = (Get-Date).AddSeconds($WatchSeconds)
$jobId = $null
while ((Get-Date) -lt $watchDeadline) {
    $jobQueryScript = @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -Atqc "
  SELECT j.id
  FROM jobs j
  WHERE j.type = 'export_csv'
    AND j.status = 'running'
    AND j.created_at >= TIMESTAMPTZ '$startedAt'
  ORDER BY j.created_at DESC
  LIMIT 1;
"
"@
    $jobOutput = Invoke-WslBash -Quiet -Script $jobQueryScript
    $jobLine = $jobOutput | Where-Object { $_ -match '^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$' } | Select-Object -Last 1
    if ($jobLine) {
        $jobId = $jobLine.ToString().Trim()
        break
    }
    Start-Sleep -Milliseconds 250
}

if (-not $jobId) {
    throw "Aucun nouvel export running n'a été observé pendant $WatchSeconds secondes."
}

$workerScript = @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime ps -q worker | head -n 1
"@
$workerOutput = Invoke-WslBash -Quiet -Script $workerScript
$workerLine = $workerOutput | Where-Object { $_ -match '^[0-9a-f]{12,64}$' } | Select-Object -Last 1
if (-not $workerLine) {
    throw "Le worker unique est introuvable au moment de l'interruption."
}
$workerId = $workerLine.ToString().Trim()

$killScript = @"
set -euo pipefail
docker update --restart=no '$workerId' >/dev/null
docker kill --signal KILL '$workerId' >/dev/null
"@
Invoke-WslBash -Script $killScript | Out-Null
Write-Host "Worker interrompu pendant running. job_id=$jobId"
Release-E2E05ExportLock
Write-Host 'Verrou de test libéré. Le prochain worker pourra reprendre après expiration du bail.'

for ($remaining = $LeaseWaitSeconds; $remaining -gt 0; $remaining -= 10) {
    $delay = [Math]::Min(10, $remaining)
    Write-Host "Attente de l'expiration du bail : $remaining s restantes..."
    Start-Sleep -Seconds $delay
}

$restartScript = @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime up -d --force-recreate --scale worker=2 worker
"@
Invoke-WslBash -Script $restartScript | Out-Null
Write-Host 'Deux workers sont relancés. Vérification de la reprise...'

$finishDeadline = (Get-Date).AddSeconds($WatchSeconds)
$summary = $null
$lastSummary = $null
while ((Get-Date) -lt $finishDeadline) {
    $summaryScript = @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -Atqc "
  SELECT j.status || '|' || j.attempt_count || '|' ||
         (SELECT count(*) FROM export_artifacts a WHERE a.export_id = j.subject_id)
  FROM jobs j
  WHERE j.id = '$jobId';
"
"@
    $summaryOutput = Invoke-WslBash -Quiet -Script $summaryScript
    $summary = $summaryOutput | Where-Object { $_ -match '^(queued|running|succeeded|failed)\|\d+\|\d+$' } | Select-Object -Last 1
    if ($summary -and $summary -ne $lastSummary) {
        Write-Host "État du job : $summary"
        $lastSummary = $summary
    }
    if ($summary -match '^(succeeded|failed)\|') {
        break
    }
    Start-Sleep -Seconds 1
}

$temporaryScript = @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime exec -T worker sh -lc "if [ -d /app/.runtime/imports/exports ]; then find /app/.runtime/imports/exports -maxdepth 1 -name '.*.tmp' -type f -printf '.' | wc -c; else echo 0; fi"
"@
$temporaryOutput = Invoke-WslBash -Quiet -Script $temporaryScript
$temporaryLine = $temporaryOutput | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1
$temporaryCount = if ($temporaryLine) { $temporaryLine.ToString().Trim() } else { '?' }

$parts = if ($summary) { $summary.ToString().Trim().Split('|') } else { @() }
$status = if ($parts.Count -ge 1) { $parts[0] } else { '' }
$attemptCount = if ($parts.Count -ge 2) { $parts[1] } else { '' }
$artifactCount = if ($parts.Count -ge 3) { $parts[2] } else { '' }

Write-Host "E2E-05 résultat : job_id=$jobId status=$status attempt_count=$attemptCount artifacts=$artifactCount temporary_files=$temporaryCount"
if ($status -eq 'succeeded' -and $attemptCount -match '^\d+$' -and [int]$attemptCount -ge 2 -and $artifactCount -eq '1' -and $temporaryCount -eq '0') {
    Write-Host 'E2E-05 PASS : reprise observée, artefact unique et aucun provisoire.'
}
else {
    throw 'E2E-05 NON VALIDE : conserver ce résumé et ne pas déclarer PASS.'
}
}
finally {
    Release-E2E05ExportLock
}
