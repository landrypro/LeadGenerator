[CmdletBinding()]
param(
    [ValidatePattern('^https?://')]
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

    [ValidatePattern('^https?://')]
    [string]$PublicOrigin = 'http://localhost:5173',

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$AccountEmail,

    [ValidateSet('auto', 'tenant', 'platform', 'all')]
    [string]$Scope = 'auto',

    [ValidateRange(1, 90)]
    [int]$Days = 30,

    [ValidatePattern('^$|^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')]
    [string]$Action = '',

    [ValidateRange(1, 100)]
    [int]$Limit = 50
)

$ErrorActionPreference = 'Stop'
$apiRoot = $ApiBaseUrl.TrimEnd('/')
$credential = Get-Credential -UserName $AccountEmail -Message 'Mot de passe du compte de test'
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential.Password)
$webSession = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$originHeaders = @{ Origin = $PublicOrigin }

function ConvertTo-Utf8JsonBody {
    param([Parameter(Mandatory = $true)][hashtable]$Value)
    [byte[]]$bytes = [System.Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Compress))
    Write-Output -NoEnumerate $bytes
}

function Invoke-Utf8JsonRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [ValidateSet('Get', 'Post')][string]$Method = 'Get',
        [hashtable]$Headers,
        [byte[]]$Body
    )
    $request = @{
        Uri = $Uri
        Method = $Method
        WebSession = $webSession
        UseBasicParsing = $true
    }
    if ($Headers) { $request.Headers = $Headers }
    if ($null -ne $Body) {
        $request.ContentType = 'application/json; charset=utf-8'
        $request.Body = $Body
    }
    $response = Invoke-WebRequest @request
    [byte[]]$responseBytes = $response.RawContentStream.ToArray()
    $json = [System.Text.Encoding]::UTF8.GetString($responseBytes)
    return [PSCustomObject]@{ Body = ($json | ConvertFrom-Json); Headers = $response.Headers }
}

try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $login = Invoke-Utf8JsonRequest `
        -Uri "$apiRoot/api/auth/login" `
        -Method Post `
        -Headers $originHeaders `
        -Body (ConvertTo-Utf8JsonBody @{ email = $credential.UserName; password = $password })
} finally {
    $password = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}

$authentication = $login.Body
$canReadTenant = $authentication.capabilities -contains 'audit:read'
$canReadPlatform = $authentication.capabilities -contains 'platform:audit:read'
$requestedScopes = switch ($Scope) {
    'tenant' { @('tenant') }
    'platform' { @('platform') }
    'all' { @('tenant', 'platform') }
    default {
        @(
            if ($canReadTenant) { 'tenant' }
            if ($canReadPlatform) { 'platform' }
        )
    }
}
if (-not $requestedScopes.Count) {
    throw 'Le compte ne possede aucune capacite de lecture de l audit.'
}

$occurredTo = [DateTimeOffset]::UtcNow
$occurredFrom = $occurredTo.AddDays(-$Days)

foreach ($requestedScope in $requestedScopes) {
    if ($requestedScope -eq 'tenant' -and -not $canReadTenant) {
        throw 'Le compte ne possede pas audit:read dans son organisation active.'
    }
    if ($requestedScope -eq 'platform' -and -not $canReadPlatform) {
        throw 'Le compte ne possede pas platform:audit:read.'
    }
    $path = if ($requestedScope -eq 'tenant') { '/api/audit-events' } else { '/api/platform/audit-events' }
    $parameters = @{
        limit = $Limit
        occurred_from = $occurredFrom.ToString('o')
        occurred_to = $occurredTo.ToString('o')
    }
    if ($Action) { $parameters.action = $Action }
    $query = ($parameters.GetEnumerator() | ForEach-Object {
        '{0}={1}' -f [Uri]::EscapeDataString($_.Key), [Uri]::EscapeDataString([string]$_.Value)
    }) -join '&'
    $response = Invoke-Utf8JsonRequest -Uri "$apiRoot$path`?$query"
    $cacheControl = [string]$response.Headers['Cache-Control']
    if ($cacheControl -notmatch 'no-store') {
        throw "La route $path ne porte pas Cache-Control: no-store."
    }
    $serialized = $response.Body | ConvertTo-Json -Depth 10 -Compress
    if ($serialized -match '"email"\s*:') {
        throw "La route $path expose un champ email."
    }

    Write-Host "`nPortee : $requestedScope — $($response.Body.items.Count) evenement(s) charge(s)"
    $response.Body.items | Select-Object `
        occurred_at, `
        action, `
        entity_type, `
        @{ Name = 'actor'; Expression = { if ($_.actor.kind -eq 'system') { 'Systeme' } else { $_.actor.display_name } } }, `
        @{ Name = 'entity_id'; Expression = { $_.entity_id } }

    [PSCustomObject]@{
        Scope = $requestedScope
        CacheControl = $cacheControl
        Loaded = $response.Body.items.Count
        HasNextPage = [bool]$response.Body.next_cursor
        OccurredFrom = $response.Body.occurred_from
        OccurredTo = $response.Body.occurred_to
    }
}

Write-Host "`nLe script n affiche ni cookie, ni CSRF, ni curseur de pagination."
