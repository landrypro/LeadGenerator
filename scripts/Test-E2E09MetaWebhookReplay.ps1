[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04'
)

# Le verrou crée PostgreSQL avec les rôles app/worker et teste les rejouements,
# baux et transitions terminales des jobs. Les contrôles Meta ciblés sont inclus
# dans le verrou complet et le rapport est refusé au moindre test ignoré.
& "$PSScriptRoot\Invoke-Phase46InfrastructureScenario.ps1" `
    -Scenario 'E2E-09' `
    -Description 'Contrat Meta signé et rejeu durable des jobs dans PostgreSQL isolé' `
    -RequiredTestClasses @(
        'tests.test_connector_pilot',
        'tests.test_connector_api',
        'tests.integration.test_durable_jobs'
    ) `
    -WslDistribution $WslDistribution
