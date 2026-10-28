"""Adaptateur lecture seule de la projection Billing pour la plateforme."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...application.errors import ProvisioningServiceUnavailable
from ...application.tenancy import ActorContext
from ...application.use_cases.platform_billing import (
    PlatformBillingDetail,
    PlatformBillingEvent,
    PlatformBillingIntervention,
    PlatformBillingOrganization,
    PlatformBillingPage,
)


class SqlAlchemyPlatformBillingReader:
    def __init__(self, actor_unit_of_work_factory: Callable[[ActorContext], Any]) -> None:
        self._actor_unit_of_work_factory = actor_unit_of_work_factory

    async def list_organizations(
        self, *, context: ActorContext, after: UUID | None, limit: int, state: str | None, source: str | None
    ) -> PlatformBillingPage:
        payload = await self._read_json(
            context,
            "SELECT app_private.list_platform_billing_organizations(:after,:limit,:state,:source)",
            {"after": after, "limit": limit, "state": state, "source": source},
        )
        return PlatformBillingPage(
            items=tuple(_organization(item) for item in _items(payload)),
            next_cursor=_string_or_none(payload.get("next_cursor")),
        )

    async def get_organization(self, *, context: ActorContext, organization_id: UUID) -> PlatformBillingDetail | None:
        payload = await self._read_json(
            context,
            "SELECT app_private.get_platform_billing_organization(:organization_id)",
            {"organization_id": organization_id},
        )
        if not payload:
            return None
        organization = _organization(_object(payload.get("organization")))
        events = tuple(
            PlatformBillingEvent(event_type=str(item["event_type"]), occurred_at=_datetime(item["occurred_at"]))
            for item in _items(payload, "events")
        )
        interventions = tuple(
            PlatformBillingIntervention(
                kind=str(item["kind"]),
                status=str(item["status"]),
                created_at=_datetime(item["created_at"]),
                updated_at=_datetime(item["updated_at"]),
            )
            for item in _items(payload, "interventions")
        )
        return PlatformBillingDetail(organization=organization, events=events, interventions=interventions)

    async def _read_json(
        self, context: ActorContext, statement: str, parameters: dict[str, object]
    ) -> dict[str, object]:
        try:
            async with self._actor_unit_of_work_factory(context) as unit_of_work:
                raw = await unit_of_work.session.scalar(text(statement), parameters)
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ProvisioningServiceUnavailable
        return raw


def _organization(value: dict[str, object]) -> PlatformBillingOrganization:
    return PlatformBillingOrganization(
        id=UUID(str(value["id"])),
        name=str(value["name"]),
        organization_status=str(value["organization_status"]),
        plan_code=_string_or_none(value.get("plan_code")),
        version_number=_int_or_none(value.get("version_number")),
        currency=_string_or_none(value.get("currency")),
        subscription_state=_string_or_none(value.get("subscription_state")),
        contract_state=_string_or_none(value.get("contract_state")),
        source=str(value["source"]),
        current_period_end=_datetime_or_none(value.get("current_period_end")),
        cancel_at_period_end=bool(value.get("cancel_at_period_end", False)),
        reconciliation_status=str(value["reconciliation_status"]),
    )


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProvisioningServiceUnavailable
    return value


def _items(value: dict[str, object], key: str = "items") -> list[dict[str, object]]:
    raw = value.get(key, [])
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ProvisioningServiceUnavailable
    return raw


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ProvisioningServiceUnavailable from error
    raise ProvisioningServiceUnavailable


def _datetime_or_none(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
