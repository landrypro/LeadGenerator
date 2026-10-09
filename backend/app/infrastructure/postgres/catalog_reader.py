"""Lectures P52-07 du contrat et des droits de l'organisation courante."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...application.errors import CatalogServiceUnavailable
from ...application.ports.catalog import (
    OrganizationCatalogReader,
    OrganizationCatalogView,
    OrganizationEntitlementDecisionView,
    OrganizationPlanContractView,
)
from ...application.tenancy import TenantContext
from ...domain.catalog import ContractState, CurrencyCode, EntitlementKey, EntitlementKind


class SqlAlchemyOrganizationCatalogReader(OrganizationCatalogReader):
    """Lit sous le contexte RLS de l'organisation, sans accès direct au catalogue global."""

    def __init__(self, tenant_unit_of_work_factory: Callable[[TenantContext], Any]) -> None:
        self._tenant_unit_of_work_factory = tenant_unit_of_work_factory

    async def get_current(self, *, context: TenantContext, now: datetime) -> OrganizationCatalogView:
        try:
            async with self._tenant_unit_of_work_factory(context) as unit:
                contract_row = (
                    (
                        await unit.session.execute(
                            text(
                                """
                                SELECT id, organization_id, plan_version_id, state, currency,
                                       effective_from, effective_until, version
                                FROM public.organization_plan_contracts
                                WHERE state IN ('pending', 'active', 'suspended')
                                ORDER BY effective_from DESC, created_at DESC
                                LIMIT 1
                                """
                            )
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                decisions: list[OrganizationEntitlementDecisionView] = []
                for key in EntitlementKey:
                    value = await unit.session.scalar(
                        text("SELECT app_private.tenant_effective_entitlement(:key, :now)"),
                        {"key": key.value, "now": now},
                    )
                    decisions.append(self._decision(key, value))
        except SQLAlchemyError as error:
            raise CatalogServiceUnavailable from error

        return OrganizationCatalogView(
            contract=self._contract(contract_row) if contract_row is not None else None,
            entitlements=tuple(decisions),
        )

    @staticmethod
    def _contract(row: Any) -> OrganizationPlanContractView:
        return OrganizationPlanContractView(
            id=UUID(str(row["id"])),
            organization_id=UUID(str(row["organization_id"])),
            plan_version_id=UUID(str(row["plan_version_id"])),
            state=ContractState(row["state"]),
            currency=CurrencyCode(row["currency"]),
            effective_from=row["effective_from"],
            effective_until=row["effective_until"],
            version=int(row["version"]),
        )

    @staticmethod
    def _decision(key: EntitlementKey, value: Any) -> OrganizationEntitlementDecisionView:
        if not isinstance(value, dict) or not isinstance(value.get("code"), str):
            raise CatalogServiceUnavailable("Le moteur de droits a retourné une réponse invalide.")
        raw_kind = value.get("value_kind")
        raw_provenance = value.get("provenance", [])
        provenance = tuple(
            (str(item["source"]), bool(item["applied"]))
            for item in raw_provenance
            if isinstance(item, dict) and isinstance(item.get("source"), str) and isinstance(item.get("applied"), bool)
        )
        return OrganizationEntitlementDecisionView(
            key=key,
            code=value["code"],
            value_kind=EntitlementKind(raw_kind) if raw_kind in {kind.value for kind in EntitlementKind} else None,
            integer_value=int(value["integer_value"]) if value.get("integer_value") is not None else None,
            boolean_value=bool(value["boolean_value"]) if value.get("boolean_value") is not None else None,
            source=value.get("source") if isinstance(value.get("source"), str) else None,
            reason=value.get("reason") if isinstance(value.get("reason"), str) else None,
            provenance=provenance,
        )
