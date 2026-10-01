[CmdletBinding()]
param()

& "$PSScriptRoot\Invoke-Phase46PytestScenario.ps1" `
    -Scenario 'E2E-08' `
    -Description 'Pilote Meta simulé, admission signée et contrat HTTP protégé' `
    -Tests @(
        'tests/test_connector_pilot.py',
        'tests/test_connector_api.py'
    )
