param(
    [string]$QaHost = '99.79.105.232',
    [string]$SshKeyPath = (Join-Path $env:USERPROFILE '.ssh\marketteo-staging-tunnel')
)

$ErrorActionPreference = 'Stop'
$sqlPath = Join-Path $PSScriptRoot 'Measure-QAVolumetry.sql'
if (-not (Test-Path -LiteralPath $sqlPath -PathType Leaf)) {
    throw "Fichier SQL absent : $sqlPath"
}
if (-not (Test-Path -LiteralPath $SshKeyPath -PathType Leaf)) {
    throw "Clé SSH QA absente ou inaccessible : $SshKeyPath"
}

$remoteCommand = 'cd /home/ubuntu/LeadGenerator && docker compose --env-file .env.qa -f compose.qa.yaml exec -T postgresql sh -lc ''psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'''
Get-Content -Raw -Encoding UTF8 -LiteralPath $sqlPath |
    & ssh -T -o BatchMode=yes -o ConnectTimeout=15 -i $SshKeyPath "ubuntu@$QaHost" $remoteCommand

if ($LASTEXITCODE -ne 0) {
    throw "La mesure QA a échoué (code SSH : $LASTEXITCODE)."
}
