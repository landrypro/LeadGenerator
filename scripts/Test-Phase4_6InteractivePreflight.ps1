[CmdletBinding()]
param(
    [ValidatePattern('^https?://')]
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

    [ValidatePattern('^https?://')]
    [string]$ClientBaseUrl = 'http://localhost:5173'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$apiRoot = $ApiBaseUrl.TrimEnd('/')
$clientRoot = $ClientBaseUrl.TrimEnd('/')
$fixtureDirectory = Join-Path $workspace 'docs\fixtures\phase4_6'
$requiredHeaders = @('Entreprise', 'Identifiant', 'Adresse', 'Contact', 'Fonction', 'Courriel', 'Téléphone', 'LinkedIn', 'Facebook')

function Get-JsonResponse {
    param([Parameter(Mandatory = $true)][string]$Uri)

    $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 10
    if ($response.StatusCode -ne 200) {
        throw "Réponse HTTP inattendue pour $Uri : $($response.StatusCode)."
    }
    return $response.Content | ConvertFrom-Json
}

function Test-CsvFixture {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$ExpectedRows
    )

    $path = Join-Path $fixtureDirectory $Name
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Fixture introuvable : $path"
    }
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $encoding = [System.Text.UTF8Encoding]::new($false, $true)
    try {
        [void]$encoding.GetString($bytes)
    } catch {
        throw "La fixture $Name n'est pas encodée en UTF-8 valide."
    }
    $rows = @(Import-Csv -LiteralPath $path)
    if ($rows.Count -ne $ExpectedRows) {
        throw "La fixture $Name contient $($rows.Count) ligne(s), $ExpectedRows attendue(s)."
    }
    $headers = @($rows[0].PSObject.Properties.Name)
    if (@(Compare-Object $requiredHeaders $headers).Count -ne 0) {
        throw "Les en-têtes de $Name ne correspondent pas au mapping de recette."
    }
    return [PSCustomObject]@{ Fixture = $Name; Rows = $rows.Count; Headers = $headers.Count }
}

$live = Get-JsonResponse "$apiRoot/api/health/live"
$ready = Get-JsonResponse "$apiRoot/api/health/ready"
$client = Invoke-WebRequest -UseBasicParsing -Uri $clientRoot -TimeoutSec 10
if ($client.StatusCode -ne 200) {
    throw "Client indisponible : HTTP $($client.StatusCode)."
}

$fixtures = @(
    Test-CsvFixture -Name 'P4_6_IMPORT_VALID.csv' -ExpectedRows 2
    Test-CsvFixture -Name 'P4_6_IMPORT_QUARANTAINE.csv' -ExpectedRows 2
)

[PSCustomObject]@{
    ApiLive = $live.status
    ApiReady = $ready.status
    PostgreSQL = $ready.dependencies.postgresql
    Redis = $ready.dependencies.redis
    ClientHttpStatus = $client.StatusCode
    Fixtures = $fixtures
}

