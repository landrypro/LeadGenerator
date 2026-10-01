[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$workspaceWsl = (& wsl -d $WslDistribution -- wslpath -a $workspace).Trim()
if ($LASTEXITCODE -ne 0 -or -not $workspaceWsl) {
    throw "Impossible de résoudre le répertoire WSL pour $workspace."
}
if ($workspaceWsl -match "[\r\n']") {
    throw 'Le chemin de travail WSL contient un caractère non pris en charge.'
}

function Invoke-WslBash {
    param(
        [Parameter(Mandatory)][string]$Script,
        [switch]$Quiet
    )

    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Script))
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& wsl -d $WslDistribution -- bash -lc "printf '%s' $encoded | base64 -d | bash" 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "La vérification conteneur E2E-06 a échoué (code $exitCode)."
    }
    if (-not $Quiet) {
        $output | ForEach-Object { Write-Host $_ }
    }
    return $output
}

# La vérification passe par les réseaux Docker internes. Elle ne dépend donc ni
# du port Windows 8000 ni d'un serveur Vite/API lancé hors de Docker.
Invoke-WslBash -Script @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime build --no-cache api
GOOGLE_PLACES_SIMULATOR_ENABLED=true docker compose --profile runtime up -d --force-recreate api
"@ | Out-Null

$membership = Invoke-WslBash -Quiet -Script @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -At -F '|' -c "
  SELECT m.user_id, m.organization_id, m.id
  FROM memberships m
  JOIN users u ON u.id = m.user_id
  JOIN organizations o ON o.id = m.organization_id
  WHERE m.status = 'active'
    AND u.status = 'active'
    AND o.status = 'active'
    AND m.role IN ('manager', 'admin')
  ORDER BY CASE m.role WHEN 'manager' THEN 0 ELSE 1 END, m.created_at
  LIMIT 1;
"
"@ | Where-Object { $_ -match '^[0-9a-f-]+\|[0-9a-f-]+\|[0-9a-f-]+$' } | Select-Object -Last 1

if (-not $membership) {
    throw 'Aucun membre actif de rôle manager ou admin n est disponible pour E2E-06.'
}
$memberParts = $membership -split '\|'
if ($memberParts.Count -ne 3) {
    throw 'Le membre de recette E2E-06 est illisible.'
}
foreach ($value in $memberParts) {
    if ($value -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') {
        throw 'Le membre de recette E2E-06 est invalide.'
    }
}
$userId, $organizationId, $membershipId = $memberParts

$verification = Invoke-WslBash -Script @"
set -euo pipefail
cd '$workspaceWsl'
docker compose --profile runtime exec -T \
  -e E2E_USER_ID='$userId' \
  -e E2E_ORGANIZATION_ID='$organizationId' \
  -e E2E_MEMBERSHIP_ID='$membershipId' \
  api python - <<'PY'
import asyncio
import os
from uuid import UUID

from backend.app.application.models import GoogleAccessContext, GooglePlaceSearchCriteria
from backend.app.application.tenancy import TenantContext
from backend.app.bootstrap import build_container
from backend.app.config import Settings
from backend.app.infrastructure.google.simulated import SimulatedGooglePlacesGateway
from backend.app.infrastructure.postgres.models.usage import UsageDailyCounterModel, UsageOperationEventModel


def operation_totals(report, code):
    return next(item for item in report["google"]["totals"] if item["code"] == code)


async def report(container, context, membership_id, scope):
    assert container.get_usage_report is not None
    return await container.get_usage_report.execute(
        context=context,
        membership_id=membership_id,
        scope=scope,
        owner_membership_id=None,
        period="today",
        start_on=None,
        end_on=None,
        group_by="day",
        can_read_self=True,
        can_read_organization=True,
    )


async def main():
    settings = Settings.from_env()
    assert settings.google_places_simulator_enabled
    container = build_container(settings)
    assert isinstance(container.search_google_places._places, SimulatedGooglePlacesGateway)
    assert container.search_google_places._issue_map_snapshot is False
    assert container.get_current_usage is not None
    assert container.usage_store is not None

    user_id = UUID(os.environ["E2E_USER_ID"])
    organization_id = UUID(os.environ["E2E_ORGANIZATION_ID"])
    membership_id = UUID(os.environ["E2E_MEMBERSHIP_ID"])
    context = TenantContext(user_id, organization_id, "e2e06-container-verification")
    access = GoogleAccessContext(user_id, organization_id, membership_id)

    before_current_self = await container.get_current_usage.execute(
        context=context, scope="self", can_read_self=True, can_read_organization=True
    )
    before_current_org = await container.get_current_usage.execute(
        context=context, scope="organization", can_read_self=True, can_read_organization=True
    )
    before_self = await report(container, context, membership_id, "self")
    before_org = await report(container, context, membership_id, "organization")

    outcome = await container.search_google_places.execute(
        GooglePlaceSearchCriteria(
            query="plombier",
            center_latitude=46.8139,
            center_longitude=-71.2080,
            radius_km=15,
            include_service_area_businesses=True,
            language_code="fr",
            region_code="CA",
        ),
        access,
    )
    assert [place.name for place in outcome.search.places] == ["Atelier simulé Alpha", "Atelier simulé Beta"]
    assert all(place.latitude is None and place.longitude is None for place in outcome.search.places)
    assert outcome.map_snapshot_token == ""
    assert outcome.selection_token

    after_current_self = await container.get_current_usage.execute(
        context=context, scope="self", can_read_self=True, can_read_organization=True
    )
    after_current_org = await container.get_current_usage.execute(
        context=context, scope="organization", can_read_self=True, can_read_organization=True
    )
    after_self = await report(container, context, membership_id, "self")
    after_org = await report(container, context, membership_id, "organization")

    assert after_current_self["used"] == before_current_self["used"] + 1
    assert after_current_org["used"] == before_current_org["used"] + 1
    for before, after in ((before_self, after_self), (before_org, after_org)):
        before_quota = operation_totals(before, "google.places_text_search.quota")
        after_quota = operation_totals(after, "google.places_text_search.quota")
        before_request = operation_totals(before, "google.places_text_search.request")
        after_request = operation_totals(after, "google.places_text_search.request")
        assert after_quota["accepted"] == before_quota["accepted"] + 1
        assert after_request["attempted"] == before_request["attempted"] + 1
        assert after_request["succeeded"] == before_request["succeeded"] + 1
        assert operation_totals(after, "google.maps_static.request") == operation_totals(
            before, "google.maps_static.request"
        )

    sensitive_names = {"query", "response", "latitude", "longitude", "cost"}
    for model in (UsageOperationEventModel, UsageDailyCounterModel):
        assert not (sensitive_names & set(model.__table__.columns.keys()))

    print("E2E06_CONTAINER=PASS")
    print("provider=simulated results=2 map_snapshot=absent")
    print(f"quota_self={before_current_self['used']}->{after_current_self['used']}")
    print(f"quota_organization={before_current_org['used']}->{after_current_org['used']}")
    print("usage=self+organization quota_reserved=+1 upstream_attempted=+1 upstream_succeeded=+1")
    print("maps_static=unchanged durable_sensitive_columns=0")


asyncio.run(main())
PY
"@

if ($verification -notcontains 'E2E06_CONTAINER=PASS') {
    throw 'La vérification conteneur E2E-06 ne confirme pas le résultat attendu.'
}
Write-Host 'E2E-06 est validé par le parcours conteneur : simulateur, quota Redis, usage PostgreSQL et absence de carte sont rapprochés.'
