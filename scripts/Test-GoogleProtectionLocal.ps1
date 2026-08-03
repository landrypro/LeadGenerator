[CmdletBinding()]
param(
    [ValidatePattern('^https?://')]
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

    [ValidatePattern('^https?://')]
    [string]$PublicOrigin = 'http://localhost:5173',

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$AdministratorEmail,

    [Parameter(Mandatory = $true)]
    [ValidateSet('RUN_ONE_GOOGLE_SEARCH')]
    [string]$ConfirmGoogleCall,

    [ValidateNotNullOrEmpty()]
    [string]$Query = 'plombier',

    [ValidateRange(-90, 90)]
    [double]$Latitude = 46.8139,

    [ValidateRange(-180, 180)]
    [double]$Longitude = -71.2080,

    [ValidateRange(1, 50)]
    [double]$RadiusKm = 15,

    [switch]$FetchMap
)

$ErrorActionPreference = 'Stop'
$apiRoot = $ApiBaseUrl.TrimEnd('/')
$webSession = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$credential = Get-Credential -UserName $AdministratorEmail -Message 'Mot de passe du membre actif'
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential.Password)
$csrfToken = $null

function ConvertTo-Utf8JsonBody {
    param([Parameter(Mandatory = $true)][hashtable]$Value)
    $json = $Value | ConvertTo-Json -Compress
    [byte[]]$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    Write-Output -NoEnumerate $bytes
}

function ConvertFrom-Utf8Response {
    param([Parameter(Mandatory = $true)]$Response)
    [byte[]]$responseBytes = $Response.RawContentStream.ToArray()
    $json = [System.Text.Encoding]::UTF8.GetString($responseBytes)
    return $json | ConvertFrom-Json
}

function Invoke-Utf8JsonRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][Microsoft.PowerShell.Commands.WebRequestSession]$Session,
        [hashtable]$Headers,
        [Parameter(Mandatory = $true)][byte[]]$Body
    )
    return Invoke-WebRequest `
        -Uri $Uri `
        -Method Post `
        -WebSession $Session `
        -Headers $Headers `
        -ContentType 'application/json; charset=utf-8' `
        -Body $Body `
        -UseBasicParsing
}

try {
    $readiness = Invoke-RestMethod -Uri "$apiRoot/api/health/ready" -Method Get
    if ($readiness.status -ne 'ready') {
        throw 'Le backend n est pas pret. Verifiez PostgreSQL et Redis.'
    }

    try {
        $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
        $loginResponse = Invoke-Utf8JsonRequest `
            -Uri "$apiRoot/api/auth/login" `
            -Session $webSession `
            -Headers @{ Origin = $PublicOrigin } `
            -Body (ConvertTo-Utf8JsonBody @{ email = $credential.UserName; password = $password })
        $authentication = ConvertFrom-Utf8Response $loginResponse
    } finally {
        $password = $null
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }

    if (-not $authentication.active_organization) {
        throw 'Le compte ne possede aucune organisation active.'
    }
    if ($authentication.capabilities -notcontains 'google:search') {
        throw 'Le compte ne possede pas la capacite google:search.'
    }
    if ($FetchMap -and $authentication.capabilities -notcontains 'google:map') {
        throw 'Le compte ne possede pas la capacite google:map.'
    }
    $csrfToken = $authentication.csrf_token
    if (-not $csrfToken) {
        throw 'La connexion n a pas retourne la protection CSRF attendue.'
    }

    $searchResponse = Invoke-Utf8JsonRequest `
        -Uri "$apiRoot/api/google/places/search" `
        -Session $webSession `
        -Headers @{ Origin = $PublicOrigin; 'X-CSRF-Token' = $csrfToken } `
        -Body (ConvertTo-Utf8JsonBody @{
            query = $Query
            center_latitude = $Latitude
            center_longitude = $Longitude
            radius_km = $RadiusKm
            include_service_area_businesses = $true
            language_code = 'fr'
            region_code = 'CA'
        })
    $search = ConvertFrom-Utf8Response $searchResponse

    if ($search.places.Count -gt 20) {
        throw 'La reponse depasse la limite de 20 etablissements.'
    }
    if ($search.stats.api_calls -ne 1) {
        throw 'La reponse ne confirme pas exactement un appel Google.'
    }
    foreach ($place in $search.places) {
        $properties = $place.PSObject.Properties.Name
        if ($properties -contains 'phone' -or $properties -contains 'international_phone' -or $properties -contains 'website') {
            throw 'Un champ de contact interdit est present dans la reponse.'
        }
    }
    if (($searchResponse.Headers['Cache-Control'] -join ',') -notmatch 'no-store') {
        throw 'La reponse de recherche ne porte pas Cache-Control: no-store.'
    }

    $mapCalls = 0
    if ($FetchMap) {
        $mapResponse = Invoke-Utf8JsonRequest `
            -Uri "$apiRoot/api/map/snapshot" `
            -Session $webSession `
            -Headers @{ Origin = $PublicOrigin; 'X-CSRF-Token' = $csrfToken } `
            -Body (ConvertTo-Utf8JsonBody @{ token = $search.map_snapshot_token })
        if (($mapResponse.Headers['Cache-Control'] -join ',') -notmatch 'no-store') {
            throw 'La reponse de carte ne porte pas Cache-Control: no-store.'
        }
        if (($mapResponse.Headers['Content-Type'] -join ',') -notmatch '^image/') {
            throw 'La route de carte n a pas retourne une image.'
        }
        $mapCalls = 1
    }

    [PSCustomObject]@{
        Status = 'ok'
        ConnectedUser = $authentication.user.email
        Organization = $authentication.active_organization.name
        GoogleCalls = $search.stats.api_calls
        MapCalls = $mapCalls
        ResultCount = $search.places.Count
        MaximumResults = 20
        ContactsAbsent = $true
        NoStore = $true
    }
    Write-Host 'Une seule recherche Google a ete executee. Aucun cookie, CSRF, jeton de carte ou secret n a ete affiche.'
} finally {
    if ($csrfToken) {
        try {
            Invoke-Utf8JsonRequest `
                -Uri "$apiRoot/api/auth/logout" `
                -Session $webSession `
                -Headers @{ Origin = $PublicOrigin; 'X-CSRF-Token' = $csrfToken } `
                -Body (ConvertTo-Utf8JsonBody @{}) | Out-Null
        } catch {
            Write-Warning 'La session de test n a pas pu etre fermee automatiquement.'
        }
    }
    $csrfToken = $null
    $authentication = $null
    $search = $null
}
