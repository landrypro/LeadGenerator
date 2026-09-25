from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from ...config import Settings
from .job_queue import _set_tenant


class ConnectorContractNotFound(ValueError):
    pass


class ConnectorContractConflict(ValueError):
    pass


class MetaConnectorManagement:
    """Tenant-scoped register for the single reviewed Meta Lead Ads pilot."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self._sessions = session_factory
        self._settings = settings

    async def list(self, context: TenantContext) -> tuple[Mapping[str, object], ...]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            rows = await session.execute(
                text("""
                    SELECT c.id, c.provider_id, c.status, c.requested_permissions, c.approved_permissions,
                           c.review_valid_until, c.created_at, c.updated_at, c.version,
                           b.id AS binding_id, b.status AS binding_status, b.allow_full_name,
                           b.allow_email, b.allow_phone, b.email_permission_status, b.phone_permission_status
                    FROM provider_connector_contracts c
                    LEFT JOIN provider_connector_bindings b ON b.contract_id = c.id AND b.organization_id = c.organization_id
                    WHERE c.connector_code = 'meta_lead_ads'
                    ORDER BY c.updated_at DESC, c.id DESC
                """),
            )
            return tuple(dict(row) for row in rows.mappings().all())

    async def ingestions(self, context: TenantContext, contract_id: UUID) -> tuple[Mapping[str, object], ...]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            rows = await session.execute(
                text("""
                    SELECT i.id, i.status, i.attempt_count, i.error_code, i.received_at, i.finished_at, i.purged_at,
                           o.result_code
                    FROM connector_ingestions i
                    JOIN provider_connector_bindings b ON b.id = i.binding_id AND b.organization_id = i.organization_id
                    LEFT JOIN connector_ingestion_outcomes o ON o.ingestion_id = i.id AND o.organization_id = i.organization_id
                    WHERE b.contract_id = :contract_id
                    ORDER BY i.received_at DESC, i.id DESC LIMIT 100
                """),
                {"contract_id": contract_id},
            )
            return tuple(dict(row) for row in rows.mappings().all())

    async def create(
        self,
        context: TenantContext,
        membership_id: UUID,
        *,
        provider_id: UUID,
        acquisition_id: UUID,
        form_id: str,
        evidence_ref: str | None,
        requested_permissions: Sequence[str],
        allow_full_name: bool,
        allow_email: bool,
        allow_phone: bool,
        email_permission_status: str,
        phone_permission_status: str,
    ) -> Mapping[str, object]:
        permissions = _permissions(requested_permissions)
        if not allow_full_name or not form_id or len(form_id) > 128:
            raise ValueError("invalid_meta_contract")
        if len(self._settings.meta_reference_hmac_key.encode("utf-8")) < 32:
            raise ValueError("meta_reference_key_not_configured")
        if email_permission_status not in {"unknown", "allowed"} or phone_permission_status not in {
            "unknown",
            "allowed",
        }:
            raise ValueError("invalid_meta_contract")
        if (allow_email and "email" not in permissions) or (allow_phone and "phone" not in permissions):
            raise ValueError("invalid_meta_contract")
        form_fingerprint = hmac.new(
            self._settings.meta_reference_hmac_key.encode(), form_id.encode(), hashlib.sha256
        ).hexdigest()
        contract_id, binding_id = uuid4(), uuid4()
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            valid = await session.scalar(
                text("""
                    SELECT 1 FROM source_providers p JOIN acquisition_records a
                      ON a.organization_id = p.organization_id AND a.provider_id = p.id
                    WHERE p.id = :provider_id AND a.id = :acquisition_id AND a.status = 'approved'
                """),
                {"provider_id": provider_id, "acquisition_id": acquisition_id},
            )
            if valid is None:
                raise ConnectorContractConflict("provider_or_acquisition_not_approved")
            try:
                await session.execute(
                    text("""
                        INSERT INTO provider_connector_contracts (
                            id, organization_id, provider_id, connector_code, status, evidence_ref,
                            requested_permissions, approved_permissions, created_by, creator_membership_id,
                            created_at, updated_at
                        ) VALUES (
                            :contract_id, :organization_id, :provider_id, 'meta_lead_ads', 'draft', :evidence_ref,
                            CAST(:permissions AS jsonb), '[]'::jsonb, :actor_id, :membership_id,
                            clock_timestamp(), clock_timestamp()
                        )
                    """),
                    {
                        "contract_id": contract_id,
                        "organization_id": context.organization_id,
                        "provider_id": provider_id,
                        "evidence_ref": evidence_ref,
                        "permissions": _json_array(permissions),
                        "actor_id": context.actor_id,
                        "membership_id": membership_id,
                    },
                )
                await session.execute(
                    text("""
                        INSERT INTO provider_connector_bindings (
                            id, organization_id, contract_id, acquisition_id, form_fingerprint, status,
                            allow_full_name, allow_email, allow_phone, email_permission_status, phone_permission_status,
                            created_at, updated_at
                        ) VALUES (
                            :binding_id, :organization_id, :contract_id, :acquisition_id, :form_fingerprint, 'draft',
                            :allow_full_name, :allow_email, :allow_phone, :email_permission_status, :phone_permission_status,
                            clock_timestamp(), clock_timestamp()
                        )
                    """),
                    {
                        "binding_id": binding_id,
                        "organization_id": context.organization_id,
                        "contract_id": contract_id,
                        "acquisition_id": acquisition_id,
                        "form_fingerprint": form_fingerprint,
                        "allow_full_name": allow_full_name,
                        "allow_email": allow_email,
                        "allow_phone": allow_phone,
                        "email_permission_status": email_permission_status,
                        "phone_permission_status": phone_permission_status,
                    },
                )
            except Exception as error:
                if "unique" in type(error).__name__.lower():
                    raise ConnectorContractConflict("duplicate_meta_connector") from error
                raise
        return {"id": contract_id, "binding_id": binding_id, "status": "draft", "version": 1}

    async def submit(self, context: TenantContext, contract_id: UUID, version: int) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            row = await session.execute(
                text("""
                    UPDATE provider_connector_contracts
                    SET status = 'pending_review', updated_at = clock_timestamp(), version = version + 1
                    WHERE id = :id AND status = 'draft' AND version = :version AND created_by = :actor_id
                    RETURNING id, status, version
                """),
                {"id": contract_id, "version": version, "actor_id": context.actor_id},
            )
            result = row.mappings().one_or_none()
            if result is None:
                raise ConnectorContractConflict("contract_not_draft_or_version")
            return dict(result)

    async def review(
        self,
        context: TenantContext,
        membership_id: UUID,
        contract_id: UUID,
        version: int,
        *,
        approve: bool,
        approved_permissions: Sequence[str],
        review_valid_until: datetime | None,
    ) -> Mapping[str, object]:
        permissions = _permissions(approved_permissions)
        if approve and (
            "full_name" not in permissions
            or review_valid_until is None
            or review_valid_until.tzinfo is None
            or review_valid_until <= datetime.now(review_valid_until.tzinfo)
        ):
            raise ValueError("invalid_meta_review")
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            contract = await session.execute(
                text("SELECT * FROM provider_connector_contracts WHERE id = :id FOR UPDATE"), {"id": contract_id}
            )
            row = contract.mappings().one_or_none()
            if row is None:
                raise ConnectorContractNotFound("contract_not_found")
            if row["status"] != "pending_review" or row["version"] != version or row["created_by"] == context.actor_id:
                raise ConnectorContractConflict("review_separation_or_version")
            requested = row["requested_permissions"]
            if not isinstance(requested, list) or not set(permissions).issubset(set(requested)):
                raise ConnectorContractConflict("approved_permissions_not_requested")
            if approve:
                ready = await session.scalar(
                    text("""
                        SELECT 1 FROM source_providers p
                        JOIN provider_connector_bindings b ON b.contract_id = :id AND b.organization_id = p.organization_id
                        JOIN acquisition_records a ON a.id = b.acquisition_id AND a.organization_id = b.organization_id
                        WHERE p.id = :provider_id AND p.status = 'active' AND p.rights_attested_at IS NOT NULL
                          AND a.status = 'approved'
                    """),
                    {"id": contract_id, "provider_id": row["provider_id"]},
                )
                if ready is None:
                    raise ConnectorContractConflict("provider_or_acquisition_not_approved")
            status = "approved" if approve else "draft"
            result = await session.execute(
                text("""
                    UPDATE provider_connector_contracts
                    SET status = :status, approved_permissions = CAST(:permissions AS jsonb),
                        reviewed_by = :actor_id, reviewer_membership_id = :membership_id,
                        review_valid_until = :review_valid_until, updated_at = clock_timestamp(), version = version + 1
                    WHERE id = :id RETURNING id, status, version, review_valid_until
                """),
                {
                    "id": contract_id,
                    "status": status,
                    "permissions": _json_array(permissions),
                    "actor_id": context.actor_id,
                    "membership_id": membership_id,
                    "review_valid_until": review_valid_until,
                },
            )
            await session.execute(
                text("""
                    UPDATE provider_connector_bindings SET status = :binding_status,
                      last_verified_at = CASE WHEN :approve THEN clock_timestamp() ELSE last_verified_at END,
                      updated_at = clock_timestamp(), version = version + 1
                    WHERE contract_id = :id
                """),
                {"id": contract_id, "binding_status": "active" if approve else "draft", "approve": approve},
            )
            return dict(result.mappings().one())

    async def disable(self, context: TenantContext, contract_id: UUID) -> None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            updated = await session.execute(
                text("""
                    UPDATE provider_connector_bindings SET status = 'disabled', disabled_at = clock_timestamp(),
                      updated_at = clock_timestamp(), version = version + 1
                    WHERE contract_id = :id AND status <> 'disabled' RETURNING id
                """),
                {"id": contract_id},
            )
            await session.execute(
                text("""
                    UPDATE provider_connector_contracts SET status = 'suspended', updated_at = clock_timestamp(), version = version + 1
                    WHERE id = :id AND status = 'approved'
                """),
                {"id": contract_id},
            )
            if updated.scalar_one_or_none() is None:
                raise ConnectorContractNotFound("active_binding_not_found")


def _permissions(values: Sequence[str]) -> tuple[str, ...]:
    allowed = {"full_name", "email", "phone"}
    normalized = tuple(sorted({value for value in values if isinstance(value, str)}))
    if not normalized or any(value not in allowed for value in normalized):
        raise ValueError("invalid_meta_permissions")
    return normalized


def _json_array(values: Sequence[str]) -> str:
    import json

    return json.dumps(list(values), separators=(",", ":"))
