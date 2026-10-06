"""Tenant-bound administration of the Automation organization switch."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from .automation_preflight import _set_tenant


class AutomationSettingsUnavailable(RuntimeError):
    """The settings command could not be persisted safely."""


class AutomationSettingsRejected(RuntimeError):
    """The current actor or organization cannot change the switch."""


class AutomationSettingsVersionConflict(RuntimeError):
    """The client attempted to update a stale settings version."""

    def __init__(self, current_version: int) -> None:
        super().__init__("La configuration Automation a été modifiée.")
        self.current_version = current_version


@dataclass(frozen=True, slots=True)
class AutomationSettingsView:
    id: UUID | None
    organization_id: UUID
    automation_enabled: bool
    suspension_generation: int
    version: int
    created_at: datetime | None
    updated_at: datetime | None


class AutomationOrganizationSettings:
    """Reads settings under tenant RLS and updates them through a DB function."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, *, context: TenantContext) -> AutomationSettingsView:
        try:
            async with self._sessions.begin() as session:
                await _set_tenant(session, context)
                row = (
                    await session.execute(
                        text(
                            """
                            SELECT id, organization_id, automation_enabled, suspension_generation,
                                   version, created_at, updated_at
                            FROM public.automation_organization_settings
                            WHERE organization_id = :organization_id
                            """
                        ),
                        {"organization_id": context.organization_id},
                    )
                ).mappings().first()
        except SQLAlchemyError as error:
            raise AutomationSettingsUnavailable from error
        if row is None:
            return AutomationSettingsView(
                id=None,
                organization_id=context.organization_id,
                automation_enabled=False,
                suspension_generation=0,
                version=0,
                created_at=None,
                updated_at=None,
            )
        return AutomationSettingsView(
            id=row["id"],
            organization_id=row["organization_id"],
            automation_enabled=bool(row["automation_enabled"]),
            suspension_generation=int(row["suspension_generation"]),
            version=int(row["version"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def update(
        self,
        *,
        context: TenantContext,
        automation_enabled: bool,
        expected_version: int,
    ) -> AutomationSettingsView:
        if expected_version < 0:
            raise ValueError("La version attendue est invalide.")
        try:
            async with self._sessions.begin() as session:
                await _set_tenant(session, context)
                raw = await session.scalar(
                    text(
                        """
                        SELECT app_private.set_automation_organization_settings(
                          :automation_enabled, :expected_version, :request_id
                        )
                        """
                    ),
                    {
                        "automation_enabled": automation_enabled,
                        "expected_version": expected_version,
                        "request_id": context.request_id,
                    },
                )
        except SQLAlchemyError as error:
            raise AutomationSettingsUnavailable from error
        payload = _json(raw)
        code = str(payload.get("code", ""))
        if code == "version_conflict":
            raise AutomationSettingsVersionConflict(int(payload.get("current_version", 0)))
        if code in {"forbidden", "invalid_contract"}:
            raise AutomationSettingsRejected(code)
        if code != "completed":
            raise AutomationSettingsUnavailable(code or "settings_update_failed")
        return AutomationSettingsView(
            id=UUID(str(payload["id"])),
            organization_id=context.organization_id,
            automation_enabled=bool(payload["automation_enabled"]),
            suspension_generation=int(payload["suspension_generation"]),
            version=int(payload["version"]),
            created_at=None,
            updated_at=None,
        )


def _json(value: Any) -> dict[str, Any]:
    return dict(json.loads(value) if isinstance(value, str) else value or {})
