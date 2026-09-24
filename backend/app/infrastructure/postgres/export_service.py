"""Tenant-scoped admission, CSV generation and private artifact lifecycle for 4.3."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.audit_events import tenant_audit_event
from ...application.tenancy import TenantContext
from ...application.use_cases.export_contract import (
    DATASETS,
    MAX_ACTIVE_EXPORTS,
    MAX_EXPORT_BYTES,
    MAX_EXPORT_ROWS,
    MAX_ORG_ARTIFACT_BYTES,
    SCHEMA_CODE,
    build_query,
    canonical_columns,
    csv_row,
    profile_columns,
    validate_filters,
)
from ...domain.audit import AuditAction, AuditActorKind, AuditSource
from ...domain.identity import CAPABILITIES_BY_ROLE, MembershipRole
from ...domain.prospect import CONTROLLED_PURPOSES
from .audit_recorder import SqlAlchemyAuditRecorder
from .job_queue import ClaimedJob, PostgresJobQueue, _set_tenant

LOGGER = logging.getLogger("marketteo.exports")


class ExportNotFound(Exception):
    pass


class ExportForbidden(Exception):
    pass


class ExportConflict(Exception):
    pass


class ExportCapacityExceeded(Exception):
    pass


class ExportExpired(Exception):
    pass


class ExportLimitExceeded(Exception):
    pass


class ExportService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], private_root: str, secret: bytes) -> None:
        if len(secret) < 32:
            raise ValueError("Secret d’idempotence des exports invalide.")
        self._sessions = sessions
        self._root = Path(private_root).resolve() / "exports"
        self._secret = secret
        self._queue = PostgresJobQueue(sessions)
        self._reconcile_after: UUID | None = None

    async def create(
        self,
        *,
        context: TenantContext,
        membership_id: UUID,
        timezone_name: str,
        dataset_code: str,
        scope: str,
        filters: dict[str, Any],
        columns: list[str] | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if dataset_code not in DATASETS or scope not in {"self", "organization"}:
            raise ValueError("invalid_dataset_or_scope")
        if not 1 <= len(idempotency_key) <= 128 or any(ord(char) < 32 or ord(char) == 127 for char in idempotency_key):
            raise ValueError("invalid_idempotency_key")
        dataset = DATASETS[dataset_code]
        chosen = canonical_columns(dataset, columns)
        clean_filters = validate_filters(dataset, filters, timezone_name=timezone_name)
        if (
            scope == "self"
            and "owner_membership_id" in clean_filters
            and clean_filters["owner_membership_id"] != str(membership_id)
        ):
            raise ValueError("scope_forbidden")
        body = {
            "dataset": dataset_code,
            "scope": scope,
            "filters": clean_filters,
            "columns": chosen,
            "schema": SCHEMA_CODE,
        }
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        scoped_key = f"{context.actor_id}:{idempotency_key}"
        digest = hmac.new(self._secret, scoped_key.encode(), hashlib.sha256).hexdigest()
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            role = await self._role(session, context, membership_id)
            self._require_dataset_role(role, dataset_code, scope)
            if "owner_membership_id" in clean_filters:
                owner = UUID(clean_filters["owner_membership_id"])
                exists = (
                    await session.execute(
                        text("""
                    SELECT 1 FROM memberships WHERE id = :id AND organization_id = :org
                """),
                        {"id": owner, "org": context.organization_id},
                    )
                ).scalar_one_or_none()
                if exists is None:
                    raise ValueError("invalid_filter")
            # Serializes idempotency, active count and stored-byte reservations per organization.
            await session.execute(
                text("SELECT id FROM organizations WHERE id = :id FOR UPDATE"), {"id": context.organization_id}
            )
            previous = (
                (
                    await session.execute(
                        text("""
                SELECT id, request_fingerprint FROM export_requests
                WHERE organization_id = :org AND idempotency_digest = :digest
            """),
                        {"org": context.organization_id, "digest": digest},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if previous is not None:
                if previous["request_fingerprint"] != fingerprint:
                    raise ExportConflict
                return await self._get_in_session(session, context, UUID(str(previous["id"])))
            active = (
                await session.execute(
                    text("""
                SELECT count(*) FROM export_requests WHERE organization_id = :org
                  AND status IN ('queued','running')
            """),
                    {"org": context.organization_id},
                )
            ).scalar_one()
            used = (
                await session.execute(
                    text("""
                SELECT COALESCE(sum(a.byte_size), 0) FROM export_artifacts a
                JOIN export_requests r ON r.id = a.export_id
                WHERE r.organization_id = :org AND r.status = 'ready'
                  AND a.deleted_at IS NULL AND a.expires_at > clock_timestamp()
            """),
                    {"org": context.organization_id},
                )
            ).scalar_one()
            if (
                int(active) >= MAX_ACTIVE_EXPORTS
                or int(used) + (int(active) + 1) * MAX_EXPORT_BYTES > MAX_ORG_ARTIFACT_BYTES
            ):
                raise ExportCapacityExceeded
            export_id = uuid4()
            await session.execute(
                text("""
                INSERT INTO export_requests (id, organization_id, requester_user_id, requester_membership_id,
                    dataset, schema_code, scope, filters, columns, request_fingerprint,
                    idempotency_digest, status, created_at)
                VALUES (:id, :org, :actor, :membership, :dataset, :schema, :scope,
                    CAST(:filters AS jsonb), CAST(:columns AS jsonb), :fingerprint,
                    :digest, 'queued', clock_timestamp())
            """),
                {
                    "id": export_id,
                    "org": context.organization_id,
                    "actor": context.actor_id,
                    "membership": membership_id,
                    "dataset": dataset_code,
                    "schema": SCHEMA_CODE,
                    "scope": scope,
                    "filters": json.dumps(clean_filters),
                    "columns": json.dumps(chosen),
                    "fingerprint": fingerprint,
                    "digest": digest,
                },
            )
            job_id = await self._queue.enqueue(
                session,
                context=context,
                job_type="export_csv",
                schema_version=1,
                subject_type="export_request",
                subject_id=export_id,
                actor_membership_id=membership_id,
                idempotency_key=digest,
                fingerprint=fingerprint,
                hmac_secrets={1: self._secret},
                active_secret_version=1,
            )
            await session.execute(
                text("UPDATE export_requests SET job_id = :job WHERE id = :id"), {"job": job_id, "id": export_id}
            )
            await SqlAlchemyAuditRecorder(session).record(
                tenant_audit_event(
                    context,
                    AuditAction.EXPORT_REQUESTED,
                    export_id,
                    {"dataset": dataset_code, "scope": scope, "filters": clean_filters, "column_count": len(chosen)},
                )
            )
            return await self._get_in_session(session, context, export_id)

    async def list(
        self, context: TenantContext, membership_id: UUID, *, limit: int = 25, cursor: UUID | None = None
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            role = await self._role(session, context, membership_id)
            if "exports:create:self" not in CAPABILITIES_BY_ROLE[role]:
                raise ExportForbidden
            anchor = None
            if cursor:
                anchor = (
                    await session.execute(
                        text("""
                    SELECT created_at FROM export_requests WHERE id = :id AND requester_user_id = :actor
                """),
                        {"id": cursor, "actor": context.actor_id},
                    )
                ).scalar_one_or_none()
                if anchor is None:
                    raise ExportNotFound
            rows = (
                (
                    await session.execute(
                        text("""
                SELECT r.id, r.dataset, r.schema_code, r.scope, r.status, r.created_at,
                       r.snapshot_at, r.finished_at, r.error_code, a.row_count,
                       a.omitted_count, a.byte_size, a.expires_at
                FROM export_requests r LEFT JOIN export_artifacts a ON a.export_id = r.id
                WHERE r.requester_user_id = :actor
                  AND (CAST(:anchor_at AS timestamptz) IS NULL OR (r.created_at, r.id) < (CAST(:anchor_at AS timestamptz), :cursor))
                ORDER BY r.created_at DESC, r.id DESC LIMIT :limit
            """),
                        {"actor": context.actor_id, "anchor_at": anchor, "cursor": cursor, "limit": limit + 1},
                    )
                )
                .mappings()
                .all()
            )
            items = []
            for row in rows[:limit]:
                try:
                    self._require_dataset_role(role, str(row["dataset"]), str(row["scope"]))
                except ExportForbidden:
                    continue
                items.append(self._public_row(row))
            return {"items": items, "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None}

    async def get(self, context: TenantContext, membership_id: UUID, export_id: UUID) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            role = await self._role(session, context, membership_id)
            row = await self._get_in_session(session, context, export_id)
            self._require_dataset_role(role, str(row["dataset"]), str(row["scope"]))
            return row

    async def download(self, context: TenantContext, membership_id: UUID, export_id: UUID) -> tuple[Path, str, int]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            role = await self._role(session, context, membership_id)
            row = (
                (
                    await session.execute(
                        text("""
                SELECT r.dataset, r.scope, r.status, r.requester_membership_id,
                       a.file_ref, a.byte_size, a.sha256, a.published_at, a.expires_at, a.deleted_at
                FROM export_requests r LEFT JOIN export_artifacts a ON a.export_id = r.id
                WHERE r.id = :id AND r.requester_user_id = :actor
            """),
                        {"id": export_id, "actor": context.actor_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ExportNotFound
            self._require_dataset_role(role, str(row["dataset"]), str(row["scope"]))
            if row["requester_membership_id"] != membership_id:
                raise ExportForbidden
            if row["status"] == "expired" or (row["expires_at"] and row["expires_at"] <= datetime.now(UTC)):
                raise ExportExpired
            if row["status"] != "ready" or row["deleted_at"] is not None or not row["file_ref"]:
                raise ExportConflict
            if await self._source_changed(session, context, str(row["dataset"]), row["published_at"]):
                raise ExportForbidden
            path = self._file_path(str(row["file_ref"]))
            if not path.is_file() or path.stat().st_size != row["byte_size"]:
                raise ExportExpired
            with path.open("rb") as artifact:
                actual_digest = hashlib.file_digest(artifact, "sha256").hexdigest()
            if actual_digest != row["sha256"]:
                raise ExportExpired
            await SqlAlchemyAuditRecorder(session).record(
                tenant_audit_event(
                    context,
                    AuditAction.EXPORT_DOWNLOADED,
                    export_id,
                    {"dataset": row["dataset"], "byte_size": row["byte_size"]},
                )
            )
            return path, str(row["dataset"]), int(row["byte_size"])

    async def _get_in_session(self, session: AsyncSession, context: TenantContext, export_id: UUID) -> dict[str, Any]:
        row = (
            (
                await session.execute(
                    text("""
            SELECT r.id, r.dataset, r.schema_code, r.scope, r.status, r.created_at,
                   r.snapshot_at, r.finished_at, r.error_code, a.row_count,
                   a.omitted_count, a.byte_size, a.expires_at
            FROM export_requests r LEFT JOIN export_artifacts a ON a.export_id = r.id
            WHERE r.id = :id AND r.requester_user_id = :actor
        """),
                    {"id": export_id, "actor": context.actor_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ExportNotFound
        return self._public_row(row)

    @staticmethod
    def _public_row(row: Any) -> dict[str, Any]:
        result = dict(row)
        if result["status"] == "ready" and result["expires_at"] and result["expires_at"] <= datetime.now(UTC):
            result["status"] = "expired"
        return result

    @staticmethod
    async def _role(session: AsyncSession, context: TenantContext, membership_id: UUID) -> MembershipRole:
        value = (
            await session.execute(
                text("""
            SELECT m.role FROM memberships m JOIN organizations o ON o.id = m.organization_id
            JOIN users u ON u.id = m.user_id
            WHERE m.id = :membership AND m.user_id = :actor AND m.organization_id = :org
              AND m.status = 'active' AND o.status = 'active' AND u.status = 'active'
        """),
                {"membership": membership_id, "actor": context.actor_id, "org": context.organization_id},
            )
        ).scalar_one_or_none()
        if value is None:
            raise ExportForbidden
        return MembershipRole(str(value))

    @staticmethod
    def _require_dataset_role(role: MembershipRole, dataset_code: str, scope: str) -> None:
        capabilities = CAPABILITIES_BY_ROLE[role]
        dataset = DATASETS[dataset_code]
        if dataset.read_capability not in capabilities or f"exports:create:{scope}" not in capabilities:
            raise ExportForbidden

    async def _source_changed(
        self, session: AsyncSession, context: TenantContext, dataset_code: str, published_at: datetime
    ) -> bool:
        if DATASETS[dataset_code].source_category is None:
            return False
        return bool(
            (
                await session.execute(
                    text("""
            SELECT EXISTS (
                SELECT 1 FROM acquisition_records WHERE organization_id = :org AND updated_at > :at
                UNION ALL SELECT 1 FROM source_providers WHERE organization_id = :org AND updated_at > :at
                UNION ALL SELECT 1 FROM source_export_rules WHERE organization_id = :org AND attested_at > :at
                UNION ALL SELECT 1 FROM source_providers WHERE organization_id = :org
                    AND valid_until > :at AND valid_until <= clock_timestamp()
                UNION ALL SELECT 1 FROM source_export_rules WHERE organization_id = :org
                    AND valid_until > :at AND valid_until <= clock_timestamp()
            )
        """),
                    {"org": context.organization_id, "at": published_at},
                )
            ).scalar_one()
        )

    def _file_path(self, file_ref: str) -> Path:
        if len(file_ref) != 48 or any(char not in "0123456789abcdef" for char in file_ref):
            raise ValueError("Référence d’artefact invalide.")
        return self._root / f"{file_ref}.csv"

    async def list_rules(self, context: TenantContext, membership_id: UUID) -> Sequence[dict[str, Any]]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            if await self._role(session, context, membership_id) is not MembershipRole.ADMIN:
                raise ExportForbidden
            rows = (
                (
                    await session.execute(
                        text("""
                SELECT id, acquisition_id, provider_id, data_category, field_codes, purpose,
                       status, valid_from, valid_until, evidence_ref, attested_at, version
                FROM source_export_rules ORDER BY attested_at DESC, id DESC LIMIT 100
            """)
                    )
                )
                .mappings()
                .all()
            )
            return [dict(row) for row in rows]

    async def set_rule(
        self,
        *,
        context: TenantContext,
        membership_id: UUID,
        acquisition_id: UUID | None,
        provider_id: UUID | None,
        category: str,
        field_codes: Sequence[str],
        purpose: str,
        status: str,
        valid_from: datetime,
        valid_until: datetime | None,
        evidence_ref: str,
        rule_id: UUID | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        valid_fields = {
            "prospect_profile": profile_columns(),
            "person_identity": frozenset({"display_name", "role_label"}),
            "channel": frozenset({"value"}),
        }
        if (acquisition_id is None) == (provider_id is None) or category not in valid_fields:
            raise ValueError("invalid_rule")
        if status not in {"allowed", "denied", "unknown"} or purpose not in CONTROLLED_PURPOSES:
            raise ValueError("invalid_rule")
        if len(set(field_codes)) != len(field_codes) or any(
            field not in valid_fields[category] for field in field_codes
        ):
            raise ValueError("invalid_rule")
        if status == "allowed" and not field_codes:
            raise ValueError("invalid_rule")
        if not 1 <= len(evidence_ref) <= 256 or any(ord(char) < 32 for char in evidence_ref):
            raise ValueError("invalid_rule")
        if valid_until is not None and valid_until <= valid_from:
            raise ValueError("invalid_rule")
        if valid_from.tzinfo is None or (valid_until is not None and valid_until.tzinfo is None):
            raise ValueError("invalid_rule")
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            if await self._role(session, context, membership_id) is not MembershipRole.ADMIN:
                raise ExportForbidden
            if acquisition_id:
                target = (
                    await session.execute(
                        text("""
                    SELECT 1 FROM acquisition_records WHERE id = :id AND status = 'approved'
                """),
                        {"id": acquisition_id},
                    )
                ).scalar_one_or_none()
            else:
                target = (
                    await session.execute(
                        text("""
                    SELECT 1 FROM source_providers WHERE id = :id AND status = 'active'
                """),
                        {"id": provider_id},
                    )
                ).scalar_one_or_none()
            if target is None:
                raise ExportNotFound
            if rule_id is None:
                rule_id = uuid4()
                row = (
                    (
                        await session.execute(
                            text("""
                    INSERT INTO source_export_rules (id, organization_id, acquisition_id, provider_id,
                        data_category, field_codes, purpose, status, valid_from, valid_until,
                        evidence_ref, attested_by, attested_at, version)
                    VALUES (:id, :org, :acquisition, :provider, :category, CAST(:fields AS jsonb),
                        :purpose, :status, :valid_from, :valid_until, :evidence,
                        :actor, clock_timestamp(), 1) RETURNING *
                """),
                            {
                                "id": rule_id,
                                "org": context.organization_id,
                                "acquisition": acquisition_id,
                                "provider": provider_id,
                                "category": category,
                                "fields": json.dumps(field_codes),
                                "purpose": purpose,
                                "status": status,
                                "valid_from": valid_from,
                                "valid_until": valid_until,
                                "evidence": evidence_ref,
                                "actor": context.actor_id,
                            },
                        )
                    )
                    .mappings()
                    .one()
                )
            else:
                updated_row = (
                    (
                        await session.execute(
                            text("""
                    UPDATE source_export_rules SET acquisition_id = :acquisition, provider_id = :provider,
                        data_category = :category, field_codes = CAST(:fields AS jsonb), purpose = :purpose,
                        status = :status, valid_from = :valid_from, valid_until = :valid_until,
                        evidence_ref = :evidence, attested_by = :actor,
                        attested_at = clock_timestamp(), version = version + 1
                    WHERE id = :id AND version = :version RETURNING *
                """),
                            {
                                "id": rule_id,
                                "version": expected_version,
                                "acquisition": acquisition_id,
                                "provider": provider_id,
                                "category": category,
                                "fields": json.dumps(field_codes),
                                "purpose": purpose,
                                "status": status,
                                "valid_from": valid_from,
                                "valid_until": valid_until,
                                "evidence": evidence_ref,
                                "actor": context.actor_id,
                            },
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if updated_row is None:
                    raise ExportConflict
                row = updated_row
            await SqlAlchemyAuditRecorder(session).record(
                tenant_audit_event(
                    context,
                    AuditAction.EXPORT_RULE_CHANGED,
                    rule_id,
                    {"category": category, "status": status, "field_count": len(field_codes)},
                )
            )
            return {key: value for key, value in dict(row).items() if key != "organization_id"}

    async def generate(self, claim: ClaimedJob, context: TenantContext, queue: PostgresJobQueue) -> str:
        if claim.type != "export_csv" or claim.schema_version != 1 or claim.subject_type != "export_request":
            raise ValueError("invalid_contract")
        if claim.actor_membership_id is None:
            raise ExportForbidden
        await self._set_running(context, claim.subject_id)
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        file_ref = secrets.token_hex(24)
        provisional = self._root / f".{file_ref}.tmp"
        final = self._file_path(file_ref)
        published = False
        row_count = omitted = byte_size = 0
        digest = hashlib.sha256()
        snapshot_at = datetime.now(UTC)
        try:
            async with self._sessions.begin() as session:
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                await _set_tenant(session, context)
                request = (
                    (
                        await session.execute(
                            text("""
                    SELECT dataset, scope, filters, columns, requester_membership_id, status
                    FROM export_requests WHERE id = :id AND requester_user_id = :actor
                """),
                            {"id": claim.subject_id, "actor": context.actor_id},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if request is None or request["requester_membership_id"] != claim.actor_membership_id:
                    raise ExportNotFound
                if request["status"] == "ready":
                    return "already_ready"
                role = await self._role(session, context, claim.actor_membership_id)
                dataset_code = str(request["dataset"])
                scope = str(request["scope"])
                self._require_dataset_role(role, dataset_code, scope)
                dataset = DATASETS[dataset_code]
                filters = dict(request["filters"])
                columns = tuple(request["columns"])
                if canonical_columns(dataset, list(columns)) != columns:
                    raise ValueError("invalid_contract")
                rules = await self._read_rules(session, context)
                sql, params = build_query(
                    dataset, scope=scope, filters=filters, timezone_name=await self._timezone(session, context)
                )
                params.update(
                    {"membership_id": claim.actor_membership_id, "actor_id": claim.actor_id, "snapshot_at": snapshot_at}
                )
                with provisional.open("xb") as output:
                    os.chmod(provisional, 0o600)
                    for chunk in (b"\xef\xbb\xbf", csv_row(columns, {column: column for column in columns})):
                        output.write(chunk)
                        digest.update(chunk)
                        byte_size += len(chunk)
                    stream = await session.stream(text(sql), params)
                    scanned = 0
                    async for record in stream.mappings():
                        scanned += 1
                        values = dict(record)
                        if dataset.source_category:
                            allowed = self._allowed_fields(values, dataset.source_category, rules, snapshot_at)
                            if dataset_code == "contacts" and "display_name" not in allowed:
                                omitted += 1
                                continue
                            if dataset_code == "contact_channels" and "value" not in allowed:
                                omitted += 1
                                continue
                            if dataset_code == "prospects":
                                for field in profile_columns():
                                    if field not in allowed and values.get(field) is not None:
                                        values[field] = None
                                        omitted += 1
                            elif dataset_code == "contacts" and "role_label" not in allowed:
                                values["role_label"] = None
                        if dataset_code == "activities":
                            values["contact_id"] = None  # Fail closed until linked-contact provenance is established.
                        row_count += 1
                        if row_count > MAX_EXPORT_ROWS:
                            raise ExportLimitExceeded
                        chunk = csv_row(columns, values)
                        byte_size += len(chunk)
                        if byte_size > MAX_EXPORT_BYTES:
                            raise ExportLimitExceeded
                        output.write(chunk)
                        digest.update(chunk)
                        if scanned % 1000 == 0 and (
                            not await queue.heartbeat(claim, context) or await queue.should_cancel(claim, context)
                        ):
                            raise ExportForbidden
                    output.flush()
                    os.fsync(output.fileno())
            if not await queue.heartbeat(claim, context) or await queue.should_cancel(claim, context):
                raise ExportForbidden
            os.replace(provisional, final)
            async with self._sessions.begin() as session:
                await _set_tenant(session, context)
                owned = (
                    await session.execute(
                        text("""
                    SELECT 1 FROM jobs WHERE id = :job AND owner_token = :token
                      AND status = 'running' AND lease_until > clock_timestamp() FOR UPDATE
                """),
                        {"job": claim.id, "token": claim.owner_token},
                    )
                ).scalar_one_or_none()
                if owned is None:
                    raise ExportForbidden
                current_role = await self._role(session, context, claim.actor_membership_id)
                self._require_dataset_role(current_role, dataset_code, scope)
                if await self._source_changed(session, context, dataset_code, snapshot_at):
                    raise ExportForbidden
                inserted = (
                    await session.execute(
                        text("""
                    INSERT INTO export_artifacts (export_id, organization_id, file_ref, byte_size,
                        sha256, row_count, omitted_count, published_at, expires_at)
                    VALUES (:id, :org, :ref, :bytes, :sha, :rows, :omitted,
                        clock_timestamp(), clock_timestamp() + interval '24 hours')
                    ON CONFLICT (export_id) DO NOTHING RETURNING export_id
                """),
                        {
                            "id": claim.subject_id,
                            "org": context.organization_id,
                            "ref": file_ref,
                            "bytes": byte_size,
                            "sha": digest.hexdigest(),
                            "rows": row_count,
                            "omitted": omitted,
                        },
                    )
                ).scalar_one_or_none()
                if inserted is None:
                    raise ExportConflict
                await session.execute(
                    text("""
                    UPDATE export_requests SET status = 'ready', snapshot_at = :snapshot,
                        finished_at = clock_timestamp(), error_code = NULL WHERE id = :id
                """),
                    {"id": claim.subject_id, "snapshot": snapshot_at},
                )
                event = tenant_audit_event(
                    context,
                    AuditAction.EXPORT_READY,
                    claim.subject_id,
                    {"row_count": row_count, "byte_size": byte_size, "omitted_count": omitted},
                )
                await SqlAlchemyAuditRecorder(session).record(replace(event, source=AuditSource.WORKER))
            published = True
            return "ok"
        finally:
            if provisional.exists():
                provisional.unlink()
            if not published and final.exists():
                final.unlink()

    async def mark_failed(self, context: TenantContext, export_id: UUID, error_code: str) -> None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            dataset = (
                await session.execute(
                    text("""
                UPDATE export_requests SET status = 'failed', error_code = :code,
                    finished_at = clock_timestamp()
                WHERE id = :id AND status <> 'ready' RETURNING dataset
            """),
                    {"id": export_id, "code": error_code},
                )
            ).scalar_one_or_none()
        if dataset is not None:
            await self._record_system_event(
                context, AuditAction.EXPORT_FAILED, export_id, {"dataset": dataset, "error_code": error_code}
            )

    async def mark_queued(self, context: TenantContext, export_id: UUID) -> None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            await session.execute(
                text("UPDATE export_requests SET status = 'queued' WHERE id = :id AND status = 'running'"),
                {"id": export_id},
            )

    async def mark_cancelled(self, context: TenantContext, export_id: UUID) -> None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            await session.execute(
                text("""
                    UPDATE export_requests SET status = 'cancelled', finished_at = clock_timestamp()
                    WHERE id = :id AND status IN ('queued', 'running')
                """),
                {"id": export_id},
            )

    async def cleanup(self, *, batch_size: int = 100) -> int:
        # Metadata is retained with the job; only private bytes expire here.
        async with self._sessions.begin() as session:
            rows = (
                (
                    await session.execute(
                        text("""
                SELECT * FROM app_private.expired_export_artifacts(:limit)
            """),
                        {"limit": batch_size},
                    )
                )
                .mappings()
                .all()
            )
        removed = 0
        for row in rows:
            context = TenantContext(
                actor_id=row["requester_user_id"],
                organization_id=row["organization_id"],
                request_id=f"export-cleanup-{row['export_id']}",
            )
            path = self._file_path(str(row["file_ref"]))
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            async with self._sessions.begin() as session:
                await _set_tenant(session, context)
                await session.execute(
                    text("""
                    UPDATE export_artifacts SET deleted_at = clock_timestamp()
                    WHERE export_id = :id AND deleted_at IS NULL
                """),
                    {"id": row["export_id"]},
                )
                changed = (
                    await session.execute(
                        text("""
                    UPDATE export_requests SET status = 'expired'
                    WHERE id = :id AND status = 'ready' RETURNING dataset
                """),
                        {"id": row["export_id"]},
                    )
                ).scalar_one_or_none()
            if changed is not None:
                await self._record_system_event(
                    context, AuditAction.EXPORT_EXPIRED, row["export_id"], {"dataset": changed}
                )
            removed += 1
        async with self._sessions.begin() as session:
            ready_rows = (
                (
                    await session.execute(
                        text("SELECT * FROM app_private.ready_export_artifacts(:limit, :after)"),
                        {"limit": batch_size, "after": self._reconcile_after},
                    )
                )
                .mappings()
                .all()
            )
        self._reconcile_after = (
            UUID(str(ready_rows[-1]["export_id"])) if len(ready_rows) == min(max(batch_size, 1), 100) else None
        )
        for row in ready_rows:
            path = self._file_path(str(row["file_ref"]))
            try:
                if path.is_file() and path.stat().st_size == row["byte_size"]:
                    continue
                path.unlink(missing_ok=True)
            except OSError:
                continue
            context = TenantContext(
                actor_id=row["requester_user_id"],
                organization_id=row["organization_id"],
                request_id=f"export-reconcile-{row['export_id']}",
            )
            async with self._sessions.begin() as session:
                await _set_tenant(session, context)
                await session.execute(
                    text(
                        "UPDATE export_artifacts SET deleted_at = clock_timestamp() WHERE export_id = :id AND deleted_at IS NULL"
                    ),
                    {"id": row["export_id"]},
                )
                changed = (
                    await session.execute(
                        text(
                            "UPDATE export_requests SET status = 'expired' WHERE id = :id AND status = 'ready' RETURNING dataset"
                        ),
                        {"id": row["export_id"]},
                    )
                ).scalar_one_or_none()
            if changed is not None:
                await self._record_system_event(
                    context, AuditAction.EXPORT_EXPIRED, row["export_id"], {"dataset": changed}
                )
            removed += 1
        if self._root.is_dir():
            cutoff = time.time() - 3600
            for path in self._root.iterdir():
                try:
                    if path.stat().st_mtime >= cutoff:
                        continue
                    if path.name.startswith(".") and path.suffix == ".tmp":
                        path.unlink(missing_ok=True)
                    elif path.suffix == ".csv" and len(path.stem) == 48:
                        async with self._sessions.begin() as session:
                            exists = (
                                await session.execute(
                                    text("SELECT app_private.export_artifact_exists(:ref)"), {"ref": path.stem}
                                )
                            ).scalar_one()
                        if not exists:
                            path.unlink(missing_ok=True)
                except OSError:
                    continue
        return removed

    async def _record_system_event(
        self, context: TenantContext, action: AuditAction, entity_id: UUID, metadata: dict[str, Any]
    ) -> None:
        try:
            async with self._sessions.begin() as session:
                await _set_tenant(session, context)
                await session.execute(text("SELECT set_config('app.actor_id', '', true)"))
                event = tenant_audit_event(context, action, entity_id, metadata)
                await SqlAlchemyAuditRecorder(session).record(
                    replace(
                        event,
                        actor_kind=AuditActorKind.SYSTEM,
                        actor_id=None,
                        source=AuditSource.WORKER,
                    )
                )
        except Exception as error:
            LOGGER.warning("export_system_audit_failed entity_id=%s error_type=%s", entity_id, type(error).__name__)

    async def _set_running(self, context: TenantContext, export_id: UUID) -> None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            await session.execute(
                text("""
                UPDATE export_requests SET status = 'running' WHERE id = :id AND status IN ('queued','running','failed')
            """),
                {"id": export_id},
            )

    @staticmethod
    async def _timezone(session: AsyncSession, context: TenantContext) -> str:
        value = (
            await session.execute(
                text("SELECT timezone FROM organizations WHERE id = :id"), {"id": context.organization_id}
            )
        ).scalar_one()
        return str(value)

    @staticmethod
    async def _read_rules(session: AsyncSession, context: TenantContext) -> Sequence[dict[str, Any]]:
        rows = (
            (
                await session.execute(
                    text("""
            SELECT id, acquisition_id, provider_id, data_category, field_codes, purpose,
                   status, valid_from, valid_until
            FROM source_export_rules WHERE organization_id = :org
        """),
                    {"org": context.organization_id},
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    @staticmethod
    def _allowed_fields(row: dict[str, Any], category: str, rules: Sequence[dict[str, Any]], now: datetime) -> set[str]:
        kind = row.get("_source_kind")
        if kind == "manual" or (kind is None and row.get("_prospect_origin") == "manual"):
            if "_prospect_origin" in row and row["_prospect_origin"] != "manual":
                return set()  # A profile-level edit cannot reclassify earlier external field values.
            return set(profile_columns()) | {"display_name", "role_label", "value"}
        if kind in {None, "google_maps"}:
            return set()
        acquisition_id = row.get("_acquisition_id")
        provider_id = row.get("_provider_id")
        if acquisition_id is not None and row.get("_acquisition_status") != "approved":
            return set()
        if provider_id is not None:
            if row.get("_provider_status") != "active":
                return set()
            if row.get("_provider_from") and row["_provider_from"] > now:
                return set()
            if row.get("_provider_until") and row["_provider_until"] <= now:
                return set()
        allowed: set[str] = set()
        denied: set[str] = set()
        for rule in rules:
            if rule["data_category"] != category or rule["purpose"] != row.get("_source_purpose"):
                continue
            if not (
                (rule["acquisition_id"] is not None and rule["acquisition_id"] == acquisition_id)
                or (rule["provider_id"] is not None and rule["provider_id"] == provider_id)
            ):
                continue
            if rule["valid_from"] > now or (rule["valid_until"] and rule["valid_until"] <= now):
                continue
            fields = set(rule["field_codes"])
            if rule["status"] in {"denied", "unknown"}:
                denied |= fields
            elif rule["status"] == "allowed":
                allowed |= fields
        return allowed - denied
