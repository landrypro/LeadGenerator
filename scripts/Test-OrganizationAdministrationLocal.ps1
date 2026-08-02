[CmdletBinding()]
param(
    [ValidatePattern('^https?://')]
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

    [ValidatePattern('^https?://')]
    [string]$PublicOrigin = 'http://localhost:5173',

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$AdministratorEmail,

    [ValidatePattern('^$|^[^@\s]+@[^@\s]+\.[^@\s]+$')]
    [string]$InviteeEmail = '',

    [ValidateSet('admin', 'manager', 'sales')]
    [string]$InviteeRole = 'manager',

    [ValidatePattern('^$|^[0-9a-fA-F-]{36}$')]
    [string]$MembershipId = '',

    [ValidateRange(0, 2147483647)]
    [int]$MembershipVersion = 0,

    [ValidateSet('', 'admin', 'manager', 'sales')]
    [string]$NewRole = '',

    [ValidateSet('', 'active', 'disabled')]
    [string]$NewStatus = '',

    [ValidatePattern('^$|^[0-9a-fA-F-]{36}$')]
    [string]$SwitchMembershipId = ''
)

$ErrorActionPreference = 'Stop'
$apiRoot = $ApiBaseUrl.TrimEnd('/')
$credential = Get-Credential -UserName $AdministratorEmail -Message 'Mot de passe du membre'
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential.Password)
$webSession = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$originHeaders = @{ Origin = $PublicOrigin }

function ConvertTo-Utf8JsonBody {
    param([Parameter(Mandatory = $true)][hashtable]$Value)
    $json = $Value | ConvertTo-Json -Compress
    [byte[]]$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)

    # PowerShell énumère normalement les tableaux retournés par une fonction.
    # Sans -NoEnumerate, Invoke-RestMethod reçoit une collection de nombres au
    # lieu d'un document JSON UTF-8 unique (par exemple, une erreur au champ 4).
    Write-Output -NoEnumerate $bytes
}

function Invoke-Utf8JsonRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [ValidateSet('Get', 'Post', 'Patch')][string]$Method = 'Get',
        [Parameter(Mandatory = $true)]
        [Microsoft.PowerShell.Commands.WebRequestSession]$WebSession,
        [hashtable]$Headers,
        [byte[]]$Body
    )

    $request = @{
        Uri = $Uri
        Method = $Method
        WebSession = $WebSession
        UseBasicParsing = $true
    }
    if ($Headers) {
        $request.Headers = $Headers
    }
    if ($null -ne $Body) {
        $request.ContentType = 'application/json; charset=utf-8'
        $request.Body = $Body
    }

    # Windows PowerShell 5.1 peut décoder application/json avec l'encodage
    # système. La lecture explicite des octets garantit ici le JSON UTF-8.
    $response = Invoke-WebRequest @request
    [byte[]]$responseBytes = $response.RawContentStream.ToArray()
    $json = [System.Text.Encoding]::UTF8.GetString($responseBytes)
    return $json | ConvertFrom-Json
}

try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $authentication = Invoke-Utf8JsonRequest `
        -Uri "$apiRoot/api/auth/login" `
        -Method Post `
        -WebSession $webSession `
        -Headers $originHeaders `
        -Body (ConvertTo-Utf8JsonBody @{ email = $credential.UserName; password = $password })
} finally {
    $password = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}

if (-not $authentication.csrf_token) {
    throw 'La connexion n a pas retourne de jeton CSRF.'
}

$organization = Invoke-Utf8JsonRequest -Uri "$apiRoot/api/organization" -Method Get -WebSession $webSession
$mutationHeaders = @{ Origin = $PublicOrigin; 'X-CSRF-Token' = $authentication.csrf_token }
$activeMembership = $authentication.memberships |
    Where-Object { $_.organization.id -eq $authentication.active_organization.id } |
    Select-Object -First 1
$canReadMembers = $authentication.capabilities -contains 'members:read'
$canManageMembers = $authentication.capabilities -contains 'members:manage'
$members = if ($canReadMembers) {
    Invoke-Utf8JsonRequest -Uri "$apiRoot/api/organization/members?limit=100" -Method Get -WebSession $webSession
} else {
    $null
}

[PSCustomObject]@{
    OrganizationId = $organization.id
    OrganizationName = $organization.name
    OrganizationVersion = $organization.version
    ConnectedUser = $authentication.user.email
    ActiveRole = $activeMembership.role
    CanReadMembers = $canReadMembers
    CanManageMembers = $canManageMembers
    MemberCount = if ($null -ne $members) { $members.items.Count } else { $null }
}

Write-Host "`nOrganisations accessibles :"
$authentication.memberships | Select-Object `
    @{ Name = 'membership_id'; Expression = { $_.id } }, `
    @{ Name = 'organization_id'; Expression = { $_.organization.id } }, `
    @{ Name = 'organization_name'; Expression = { $_.organization.name } }, `
    role, `
    @{ Name = 'active'; Expression = { $_.organization.id -eq $authentication.active_organization.id } }

if ($null -ne $members) {
    Write-Host "`nMembres de l organisation active :"
    $members.items | Select-Object membership_id, role, status, version, @{ Name = 'email'; Expression = { $_.user.email } }
} else {
    Write-Host "`nAnnuaire des membres non autorise pour ce role."
}

if ($authentication.capabilities -contains 'invitations:read') {
    $invitations = Invoke-Utf8JsonRequest `
        -Uri "$apiRoot/api/organization/invitations?limit=100" `
        -Method Get `
        -WebSession $webSession
    $invitations.items | Select-Object id, recipient_email, role, state, delivery_status, expires_at
}

if ($InviteeEmail) {
    if ($authentication.capabilities -notcontains 'invitations:manage') {
        throw 'Le compte connecte ne peut pas inviter de membre.'
    }
    $requestId = [Guid]::NewGuid()
    $invitation = Invoke-Utf8JsonRequest `
        -Uri "$apiRoot/api/organization/invitations" `
        -Method Post `
        -WebSession $webSession `
        -Headers $mutationHeaders `
        -Body (ConvertTo-Utf8JsonBody @{
            email = $InviteeEmail
            role = $InviteeRole
            invitation_request_id = $requestId
        })
    [PSCustomObject]@{
        InvitationRequestId = $requestId
        InvitationId = $invitation.id
        Recipient = $invitation.recipient_email
        Role = $invitation.role
        State = $invitation.state
        DeliveryStatus = $invitation.delivery_status
    }
    Write-Host 'Ouvrez http://127.0.0.1:8025 pour utiliser le lien reçu.'
    Write-Host 'Le script ne lit, n affiche et ne conserve jamais le jeton d invitation.'
}

if ($MembershipId) {
    if ($MembershipVersion -lt 1 -or (-not $NewRole -and -not $NewStatus)) {
        throw 'MembershipVersion et au moins NewRole ou NewStatus sont requis pour modifier un membre.'
    }
    $update = @{ version = $MembershipVersion }
    if ($NewRole) { $update.role = $NewRole }
    if ($NewStatus) { $update.status = $NewStatus }
    $updatedMember = Invoke-Utf8JsonRequest `
        -Uri "$apiRoot/api/organization/members/$MembershipId" `
        -Method Patch `
        -WebSession $webSession `
        -Headers $mutationHeaders `
        -Body (ConvertTo-Utf8JsonBody $update)
    $updatedMember | Select-Object membership_id, role, status, version
}

if ($SwitchMembershipId) {
    $switched = Invoke-Utf8JsonRequest `
        -Uri "$apiRoot/api/auth/switch-organization" `
        -Method Post `
        -WebSession $webSession `
        -Headers $mutationHeaders `
        -Body (ConvertTo-Utf8JsonBody @{ membership_id = $SwitchMembershipId })
    $switchedMembership = $switched.memberships |
        Where-Object { $_.organization.id -eq $switched.active_organization.id } |
        Select-Object -First 1
    [PSCustomObject]@{
        ActiveOrganizationId = $switched.active_organization.id
        ActiveOrganizationName = $switched.active_organization.name
        ActiveRole = $switchedMembership.role
        CsrfRotated = $switched.csrf_token -ne $authentication.csrf_token
    }
}
