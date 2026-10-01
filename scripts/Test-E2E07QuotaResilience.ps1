[CmdletBinding()]
param()

& "$PSScriptRoot\Invoke-Phase46PytestScenario.ps1" `
    -Scenario 'E2E-07' `
    -Description 'Quota Google, refus avant fournisseur et fermeture lors d indisponibilité' `
    -Tests @(
        'tests/test_google_quota_policy.py',
        'tests/test_search_service.py',
        'tests/integration/test_api_workflow.py'
    )
