"""Adaptateur PostgreSQL des commandes internes P52-03."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.errors import CatalogServiceUnavailable
from ...application.ports.catalog import (
    CatalogMutationResult,
    CatalogMutationResultCode,
    CatalogPlanVersionView,
    CatalogPlanView,
    OrganizationPlanContractView,
    PlanContractOverrideView,
)
from ...domain.catalog import (
    ContractState,
    CurrencyCode,
    EntitlementKey,
    EntitlementKind,
    EntitlementValue,
    OverrideState,
    PlanCode,
)


class SqlAlchemyCatalogMutations:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_plan(
        self, *, plan_id: UUID, operation_id: UUID, code: PlanCode, display_order: int, now: datetime
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "create_plan",
                {
                    "id": plan_id,
                    "operation_id": operation_id,
                    "code": code.value,
                    "display_order": display_order,
                    "now": now,
                },
            )
        )

    async def create_plan_version(
        self,
        *,
        version_id: UUID,
        operation_id: UUID,
        plan_id: UUID,
        version_number: int,
        currency: CurrencyCode,
        billing_cycle: str,
        amount_excluding_tax_minor: int,
        effective_from: datetime,
        effective_until: datetime | None,
        entitlements: tuple[EntitlementValue, ...],
        now: datetime,
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "create_plan_version",
                {
                    "id": version_id,
                    "operation_id": operation_id,
                    "plan_id": plan_id,
                    "version_number": version_number,
                    "currency": currency.value,
                    "billing_cycle": billing_cycle,
                    "amount": amount_excluding_tax_minor,
                    "effective_from": effective_from,
                    "effective_until": effective_until,
                    "entitlements": [
                        {
                            "key": item.key.value,
                            "kind": item.kind.value,
                            "integer_value": item.integer_value,
                            "boolean_value": item.boolean_value,
                        }
                        for item in entitlements
                    ],
                    "now": now,
                },
            )
        )

    async def publish_plan_version(
        self, *, version_id: UUID, operation_id: UUID, expected_version: int, now: datetime
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "publish_plan_version",
                {"id": version_id, "operation_id": operation_id, "expected_version": expected_version, "now": now},
            )
        )

    async def attach_organization_contract(
        self,
        *,
        contract_id: UUID,
        operation_id: UUID,
        organization_id: UUID,
        plan_version_id: UUID,
        state: ContractState,
        effective_from: datetime,
        effective_until: datetime | None,
        now: datetime,
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "attach_contract",
                {
                    "id": contract_id,
                    "operation_id": operation_id,
                    "organization_id": organization_id,
                    "plan_version_id": plan_version_id,
                    "state": state.value,
                    "effective_from": effective_from,
                    "effective_until": effective_until,
                    "now": now,
                },
            )
        )

    async def change_contract_state(
        self, *, contract_id: UUID, operation_id: UUID, expected_version: int, state: ContractState, now: datetime
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "change_contract_state",
                {
                    "id": contract_id,
                    "operation_id": operation_id,
                    "expected_version": expected_version,
                    "state": state.value,
                    "now": now,
                },
            )
        )

    async def propose_contract_override(
        self,
        *,
        override_id: UUID,
        operation_id: UUID,
        contract_id: UUID,
        value: EntitlementValue,
        justification: str,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "propose_contract_override",
                {
                    "id": override_id,
                    "operation_id": operation_id,
                    "contract_id": contract_id,
                    "entitlement_key": value.key.value,
                    "value_kind": value.kind.value,
                    "integer_value": value.integer_value,
                    "boolean_value": value.boolean_value,
                    "justification": justification,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "now": now,
                },
            )
        )

    async def approve_contract_override(
        self, *, override_id: UUID, operation_id: UUID, expected_version: int, now: datetime
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "approve_contract_override",
                {"id": override_id, "operation_id": operation_id, "expected_version": expected_version, "now": now},
            )
        )

    async def revoke_contract_override(
        self, *, override_id: UUID, operation_id: UUID, expected_version: int, now: datetime
    ) -> CatalogMutationResult:
        return self._result(
            await self._call(
                "revoke_contract_override",
                {"id": override_id, "operation_id": operation_id, "expected_version": expected_version, "now": now},
            )
        )

    async def _call(self, command: str, payload: dict[str, object]) -> dict[str, Any]:
        return await self._json(
            "SELECT app_private.platform_catalog_mutate(:command, CAST(:payload AS jsonb))",
            {"command": command, "payload": json.dumps(payload, default=str, separators=(",", ":"))},
        )

    async def _json(self, statement: str, params: dict[str, object]) -> dict[str, Any]:
        try:
            value = await self._session.scalar(text(statement), params)
        except Exception as error:
            raise CatalogServiceUnavailable from error
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict) or not isinstance(value.get("code"), str):
            raise CatalogServiceUnavailable("La mutation catalogue a retourné une réponse invalide.")
        return value

    @staticmethod
    def _result(value: dict[str, Any]) -> CatalogMutationResult:
        try:
            code = CatalogMutationResultCode(value["code"])
        except ValueError as error:
            raise CatalogServiceUnavailable("Le résultat de mutation catalogue est inconnu.") from error
        plan = None
        version = None
        contract = None
        contract_override = None
        if isinstance(value.get("plan"), dict):
            item = value["plan"]
            plan = CatalogPlanView(
                UUID(item["id"]),
                PlanCode(item["code"]),
                item["state"],
                int(item["display_order"]),
                int(item["version"]),
            )
        if isinstance(value.get("plan_version"), dict):
            item = value["plan_version"]
            version = CatalogPlanVersionView(
                UUID(item["id"]),
                UUID(item["plan_id"]),
                int(item["version_number"]),
                item["state"],
                CurrencyCode(item["currency"]),
                item["billing_cycle"],
                int(item["amount_excluding_tax_minor"]),
                datetime.fromisoformat(item["effective_from"]),
                datetime.fromisoformat(item["effective_until"]) if item.get("effective_until") else None,
                int(item["version"]),
            )
        if isinstance(value.get("contract"), dict):
            item = value["contract"]
            contract = OrganizationPlanContractView(
                UUID(item["id"]),
                UUID(item["organization_id"]),
                UUID(item["plan_version_id"]),
                ContractState(item["state"]),
                CurrencyCode(item["currency"]),
                datetime.fromisoformat(item["effective_from"]),
                datetime.fromisoformat(item["effective_until"]) if item.get("effective_until") else None,
                int(item["version"]),
            )
        if isinstance(value.get("contract_override"), dict):
            item = value["contract_override"]
            contract_override = PlanContractOverrideView(
                UUID(item["id"]),
                UUID(item["organization_id"]),
                UUID(item["contract_id"]),
                EntitlementKey(item["entitlement_key"]),
                EntitlementKind(item["value_kind"]),
                int(item["integer_value"]) if item.get("integer_value") is not None else None,
                bool(item["boolean_value"]) if item.get("boolean_value") is not None else None,
                OverrideState(item["state"]),
                UUID(item["requested_by_user_id"]),
                UUID(item["approved_by_user_id"]) if item.get("approved_by_user_id") else None,
                datetime.fromisoformat(item["starts_at"]),
                datetime.fromisoformat(item["ends_at"]),
                int(item["version"]),
            )
        current_version = value.get("current_version")
        return CatalogMutationResult(
            code,
            plan,
            version,
            contract,
            contract_override,
            int(current_version) if current_version is not None else None,
        )
