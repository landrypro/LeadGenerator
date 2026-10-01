[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04'
)

# La suite RLS utilise PostgreSQL réel : contexte de tenant vide, lecture croisée,
# mutation inter-organisation, réutilisation d'une connexion et rôles SQL.
& "$PSScriptRoot\Invoke-Phase46InfrastructureScenario.ps1" `
    -Scenario 'E2E-10' `
    -Description 'Rôles PostgreSQL et isolation multi-organisation dans une base temporaire' `
    -RequiredTestClasses @('tests.integration.test_tenant_rls') `
    -WslDistribution $WslDistribution
