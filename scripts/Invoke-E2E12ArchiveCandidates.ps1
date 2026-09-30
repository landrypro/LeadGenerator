[CmdletBinding()]
param(
    [ValidateSet('Preview', 'Execute')]
    [string]$Mode = 'Preview',

    [ValidateRange(0, 100)]
    [int]$ExpectedCandidateCount = 2,

    [string]$WslDistribution = 'Ubuntu-24.04',

    [ValidatePattern('^https?://[^/]+$')]
    [string]$BaseUrl = 'http://localhost:8000',

    [ValidatePattern('^https?://[^/]+$')]
    [string]$Origin = 'http://localhost:5173',

    [switch]$ConfirmPurge,

    [System.Management.Automation.PSCredential]$Credential
)

$ErrorActionPreference = 'Stop'

function Get-E2E12Candidates {
    param(
        [Parameter(Mandatory)]
        [string]$WorkspaceWsl,
        [Parameter(Mandatory)]
        [string]$Distribution
    )

    $sql = @'
SELECT p.id,
       p.organization_id,
       p.internal_alias,
       p.version,
       (SELECT count(*) FROM public.contacts c
        WHERE c.prospect_id = p.id AND c.archived_at IS NULL) AS active_contacts,
       (SELECT count(*) FROM public.contacts c
        JOIN public.contact_channels ch ON ch.contact_id = c.id
        WHERE c.prospect_id = p.id AND ch.archived_at IS NULL) AS active_channels
FROM public.prospects p
WHERE p.archived_at IS NULL
  AND (p.internal_alias LIKE 'P4-ALPHA%' OR p.internal_alias LIKE 'QA-P46-%')
ORDER BY p.internal_alias, p.id;
'@
    $encodedSql = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sql))
    $command = "printf '%s' $encodedSql | base64 -d | docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -At -F '|'"
    $output = @(& wsl -d $Distribution --cd $WorkspaceWsl bash -lc $command 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "La lecture des candidats E2E-12 a échoué : $($output -join [Environment]::NewLine)"
    }

    return @(
        $output |
            Where-Object { $_ -match '^[0-9a-fA-F-]{36}\|' } |
            ForEach-Object {
                $columns = $_.Trim().Split('|')
                if ($columns.Count -ne 6) {
                    throw "Format de candidat E2E-12 inattendu : $_"
                }
                [pscustomobject]@{
                    Id             = $columns[0]
                    OrganizationId = $columns[1]
                    InternalAlias  = $columns[2]
                    Version        = [int]$columns[3]
                    ActiveContacts = [int]$columns[4]
                    ActiveChannels = [int]$columns[5]
                }
            }
    )
}

function Invoke-E2E12ApiRequest {
    param(
        [Parameter(Mandatory)]
        [string]$Uri,
        [Parameter(Mandatory)]
        [Microsoft.PowerShell.Commands.WebRequestSession]$Session,
        [string]$Method = 'GET',
        [hashtable]$Headers = @{},
        [object]$Body
    )

    $arguments = @{
        Uri        = $Uri
        Method     = $Method
        WebSession = $Session
        Headers    = $Headers
    }
    if ($PSBoundParameters.ContainsKey('Body')) {
        $arguments.ContentType = 'application/json'
        $arguments.Body = ($Body | ConvertTo-Json -Compress)
    }
    return Invoke-RestMethod @arguments
}

$workspace = Split-Path -Parent $PSScriptRoot
$workspaceWsl = (& wsl -d $WslDistribution -- wslpath -a $workspace).Trim()
if ($LASTEXITCODE -ne 0 -or -not $workspaceWsl) {
    throw "Impossible de résoudre le répertoire WSL pour $workspace."
}

$candidates = Get-E2E12Candidates -WorkspaceWsl $workspaceWsl -Distribution $WslDistribution
Write-Host 'E2E-12 — Candidats de purge synthétiques' -ForegroundColor Cyan
if ($candidates.Count -eq 0) {
    Write-Host 'E2E12_PURGE=COMPLETE candidates=0' -ForegroundColor Green
    exit 0
}

$candidates | Format-Table Id, OrganizationId, InternalAlias, Version, ActiveContacts, ActiveChannels -AutoSize
Write-Host "E2E12_PURGE=PREVIEW candidates=$($candidates.Count)" -ForegroundColor Yellow

if ($Mode -eq 'Preview') {
    Write-Host 'Aucune session API et aucune donnée n ont été modifiées.'
    exit 0
}

if ($candidates.Count -ne $ExpectedCandidateCount) {
    throw "Le nombre de candidats ($($candidates.Count)) diffère de ExpectedCandidateCount ($ExpectedCandidateCount)."
}
if (-not $ConfirmPurge) {
    throw 'Le mode Execute exige -ConfirmPurge après vérification de la liste affichée.'
}

$confirmation = Read-Host "Tapez ARCHIVER-$($candidates.Count) pour archiver ces $($candidates.Count) candidats"
if ($confirmation -cne "ARCHIVER-$($candidates.Count)") {
    throw 'Confirmation de purge refusée. Aucune donnée n a été modifiée.'
}

if ($null -eq $Credential) {
    $Credential = Get-Credential -Message 'Compte local disposant de prospects:archive'
}
if ([string]::IsNullOrWhiteSpace($Credential.UserName)) {
    throw 'Le courriel du compte est obligatoire.'
}

$apiSession = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$currentSession = $null
try {
    $plainPassword = $Credential.GetNetworkCredential().Password
    $currentSession = Invoke-E2E12ApiRequest -Uri "$BaseUrl/api/auth/login" -Session $apiSession -Method 'POST' `
        -Headers @{ Origin = $Origin; 'Accept-Language' = 'fr-CA' } `
        -Body @{ email = $Credential.UserName; password = $plainPassword }
    $plainPassword = $null

    foreach ($candidate in $candidates) {
        if ($currentSession.active_organization.id -ne $candidate.OrganizationId) {
            $membership = @($currentSession.memberships | Where-Object { $_.organization.id -eq $candidate.OrganizationId }) |
                Select-Object -First 1
            if ($null -eq $membership) {
                throw "Le compte connecté n est pas membre de l organisation $($candidate.OrganizationId)."
            }
            $currentSession = Invoke-E2E12ApiRequest -Uri "$BaseUrl/api/auth/switch-organization" -Session $apiSession -Method 'POST' `
                -Headers @{ Origin = $Origin; 'X-CSRF-Token' = $currentSession.csrf_token } `
                -Body @{ membership_id = $membership.id }
        }
        if ($currentSession.capabilities -notcontains 'prospects:archive') {
            throw 'Le compte connecté ne possède pas la capacité prospects:archive.'
        }

        $current = Invoke-E2E12ApiRequest -Uri "$BaseUrl/api/prospects/$($candidate.Id)" -Session $apiSession
        if ($current.archived_at -ne $null -or $current.internal_alias -ne $candidate.InternalAlias) {
            throw "Le candidat $($candidate.Id) a changé depuis le prévol."
        }
        if ([int]$current.version -ne $candidate.Version) {
            throw "La version du candidat $($candidate.Id) a changé depuis le prévol."
        }

        $archived = Invoke-E2E12ApiRequest -Uri "$BaseUrl/api/prospects/$($candidate.Id)/archive" -Session $apiSession -Method 'POST' `
            -Headers @{ Origin = $Origin; 'X-CSRF-Token' = $currentSession.csrf_token } `
            -Body @{ version = $candidate.Version; archive_reason_code = 'no_longer_relevant' }
        Write-Host "E2E12_PURGE_ARCHIVED id=$($archived.prospect_id) version=$($archived.version) contacts=$($archived.contacts_archived) channels=$($archived.channels_archived)" -ForegroundColor Green
    }

    $remaining = Get-E2E12Candidates -WorkspaceWsl $workspaceWsl -Distribution $WslDistribution
    if ($remaining.Count -ne 0) {
        throw "Le contrôle final trouve encore $($remaining.Count) candidat(s) actif(s)."
    }
    Write-Host "E2E12_PURGE=PASS candidates_before=$($candidates.Count) candidates_after=0" -ForegroundColor Green
}
finally {
    $plainPassword = $null
    if ($null -ne $currentSession) {
        try {
            Invoke-E2E12ApiRequest -Uri "$BaseUrl/api/auth/logout" -Session $apiSession -Method 'POST' `
                -Headers @{ Origin = $Origin; 'X-CSRF-Token' = $currentSession.csrf_token } -Body @{} | Out-Null
        }
        catch {
            Write-Warning 'La session technique E2E-12 n a pas pu être fermée automatiquement.'
        }
    }
}
