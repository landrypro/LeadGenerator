[CmdletBinding()]
param()

$workspace = Split-Path -Parent $PSScriptRoot
$fixtureDirectory = Join-Path $workspace 'docs\fixtures\phase4_6'
$expectedHeaders = @('Entreprise', 'Identifiant', 'Adresse', 'Contact', 'Fonction', 'Courriel', 'Téléphone', 'LinkedIn', 'Facebook')

foreach ($fixture in @('P4_6_IMPORT_VALID.csv', 'P4_6_IMPORT_QUARANTAINE.csv')) {
    $path = Join-Path $fixtureDirectory $fixture
    $rows = @(Import-Csv -LiteralPath $path)
    if ($rows.Count -ne 2 -or @(Compare-Object $expectedHeaders $rows[0].PSObject.Properties.Name).Count -ne 0) {
        throw "Fixture CSV invalide : $fixture"
    }
}

& "$PSScriptRoot\Invoke-Phase46PytestScenario.ps1" `
    -Scenario 'E2E-03' `
    -Description 'Import CSV, mapping déclaré, idempotence et quarantaine' `
    -Tests @(
        'tests/test_csv_import_processing.py',
        'tests/test_retention_use_cases.py',
        'tests/test_retention_api.py'
    )
