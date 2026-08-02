[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^https?://')]
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

    [Parameter(Mandatory = $false)]
    [ValidatePattern('^https?://')]
    [string]$PublicOrigin = 'http://localhost:5173',

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$AdministratorEmail,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$OrganizationName,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[^@\s]+@[^@\s]+\.[^@\s]+$')]
    [string]$InviteeEmail,

    [Parameter(Mandatory = $false)]
    [ValidateSet('fr-CA', 'en-CA')]
    [string]$Locale = 'fr-CA',

    [Parameter(Mandatory = $false)]
    [ValidateNotNullOrEmpty()]
    [string]$Timezone = 'America/Toronto'
)

$ErrorActionPreference = 'Stop'
$apiRoot = $ApiBaseUrl.TrimEnd('/')
$credential = Get-Credential -UserName $AdministratorEmail -Message 'Mot de passe de l administrateur de plateforme'
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential.Password)

try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $webSession = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $headers = @{ Origin = $PublicOrigin }
    $loginJson = @{
        email = $credential.UserName
        password = $password
    } | ConvertTo-Json -Compress
    [byte[]]$loginBody = [System.Text.Encoding]::UTF8.GetBytes($loginJson)

    $authentication = Invoke-RestMethod `
        -Uri "$apiRoot/api/auth/login" `
        -Method Post `
        -WebSession $webSession `
        -Headers $headers `
        -ContentType 'application/json; charset=utf-8' `
        -Body $loginBody
} finally {
    $password = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}

if (-not $authentication.csrf_token) {
    throw 'La connexion n a pas retourne de jeton CSRF.'
}
if ($authentication.capabilities -notcontains 'platform:organizations:create') {
    throw 'Le compte connecte n est pas Administrateur de plateforme.'
}

$creationRequestId = [Guid]::NewGuid()
$provisioningJson = @{
    name = $OrganizationName
    locale = $Locale
    timezone = $Timezone
    first_administrator_email = $InviteeEmail
    creation_request_id = $creationRequestId
} | ConvertTo-Json -Compress
[byte[]]$provisioningBody = [System.Text.Encoding]::UTF8.GetBytes($provisioningJson)
$mutationHeaders = @{
    Origin = $PublicOrigin
    'X-CSRF-Token' = $authentication.csrf_token
}

$result = Invoke-RestMethod `
    -Uri "$apiRoot/api/platform/organizations" `
    -Method Post `
    -WebSession $webSession `
    -Headers $mutationHeaders `
    -ContentType 'application/json; charset=utf-8' `
    -Body $provisioningBody

$summary = [PSCustomObject]@{
    CreationRequestId = $creationRequestId
    OrganizationId = $result.organization.id
    OrganizationStatus = $result.organization.status
    InvitationId = $result.first_invitation.id
    InvitationState = $result.first_invitation.state
    DeliveryStatus = $result.first_invitation.delivery_status
    Replayed = $result.replayed
}
$summary

if ($result.first_invitation.delivery_status -ne 'sent') {
    throw "L invitation a ete creee, mais le courriel n a pas ete remis (statut: $($result.first_invitation.delivery_status)). Verifiez INVITATION_DELIVERY_BACKEND et la configuration SMTP."
}

Write-Host 'Ouvrez http://127.0.0.1:8025 pour verifier le courriel puis utilisez son lien.'
Write-Host 'Le script ne lit, n affiche et ne conserve jamais le jeton d invitation.'
