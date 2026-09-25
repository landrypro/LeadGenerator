from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from ...config import Settings
from .job_queue import PostgresJobQueue, _set_tenant


class MetaWebhookRejected(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MetaWebhookAdmission:
    ingestion_id: UUID
    duplicate: bool


@dataclass(frozen=True, slots=True)
class MetaLeadFields:
    full_name: str | None
    email: str | None
    phone: str | None


class MetaLeadProcessor:
    """Fetches and persists the three explicitly approved Meta Lead Ads fields only."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self._sessions = session_factory
        self._settings = settings

    async def process(self, ingestion_id: UUID, context: TenantContext) -> str:
        lead_reference, start_result = await self._start(ingestion_id, context)
        if lead_reference is None:
            return start_result
        if not self._settings.meta_lead_ads_enabled:
            raise ValueError("external_review_required")
        fields = await self._fetch(lead_reference)
        return await self._persist(ingestion_id, context, fields)

    async def _start(self, ingestion_id: UUID, context: TenantContext) -> tuple[str | None, str]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            record = await self._authorized_ingestion(session, ingestion_id)
            if record is None:
                await _terminal(session, ingestion_id, "revoked", "authorization_revoked")
                return None, "authorization_revoked"
            source_occurred_at = record["source_occurred_at"]
            if isinstance(source_occurred_at, datetime) and source_occurred_at < datetime.now(UTC).replace(
                microsecond=0
            ):
                # Meta notifications are deliberately short lived; old delivery is not imported.
                stale = await session.scalar(
                    text("SELECT :occurred < clock_timestamp() - interval '24 hours'"),
                    {"occurred": source_occurred_at},
                )
                if stale:
                    await _outcome(session, record, "quarantined")
                    await _terminal(session, ingestion_id, "quarantined", "source_event_stale")
                    return None, "quarantined"
            if record["status"] == "succeeded" or record["status"] == "quarantined":
                return None, str(record["status"])
            await session.execute(
                text("""
                    UPDATE connector_ingestions
                    SET status = 'running', attempt_count = attempt_count + 1,
                        updated_at = clock_timestamp(), version = version + 1
                    WHERE id = :id AND status IN ('queued', 'running')
                """),
                {"id": ingestion_id},
            )
            value = record["lead_reference"]
            return (str(value), "running") if value else (None, "authorization_revoked")

    async def _fetch(self, lead_reference: str) -> MetaLeadFields:
        # The response and URL are intentionally never logged: both may contain personal data or a token.
        url = f"{self._settings.meta_graph_api_base_url}/v21.0/{lead_reference}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False) as client:
                response = await client.get(
                    url,
                    params={"fields": "field_data", "access_token": self._settings.meta_graph_access_token},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("meta_dependency_unavailable") from error
        return _approved_meta_fields(payload)

    async def _persist(self, ingestion_id: UUID, context: TenantContext, fields: MetaLeadFields) -> str:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            record = await self._authorized_ingestion(session, ingestion_id)
            if record is None:
                await _terminal(session, ingestion_id, "revoked", "authorization_revoked")
                return "authorization_revoked"
            if record["status"] in {"succeeded", "quarantined"}:
                return str(record["status"])
            if not fields.full_name or not record["allow_full_name"]:
                await _outcome(session, record, "quarantined")
                await _terminal(session, ingestion_id, "quarantined", "missing_required_name")
                return "quarantined"

            now = datetime.now(UTC).replace(microsecond=0)
            provenance_id, prospect_id, contact_id = uuid4(), uuid4(), uuid4()
            await session.execute(
                text("""
                    INSERT INTO provenance_records (
                        id, organization_id, source_kind, source_label, provider_id, evidence_ref, purpose,
                        territory, obtained_at, verified_at, attested_by, acquisition_record_id, created_at
                    ) VALUES (
                        :id, :organization_id, 'facebook', :source_label, :provider_id, :evidence_ref, :purpose,
                        :territory, :now, :now, :actor_id, :acquisition_id, :now
                    )
                """),
                {**record, "id": provenance_id, "now": now},
            )
            await session.execute(
                text("""
                    INSERT INTO prospects (
                        id, organization_id, google_place_id, internal_alias, origin, source_label,
                        acquisition_record_id, owner_id, stage_code, priority, profile_provenance_id,
                        retention_review_at, created_at, updated_at
                    ) VALUES (
                        :id, :organization_id, NULL, :alias, 'connector', :source_label,
                        :acquisition_id, NULL, 'new', 0, :provenance_id, NULL, :now, :now
                    )
                """),
                {
                    **record,
                    "id": prospect_id,
                    "provenance_id": provenance_id,
                    "alias": fields.full_name[:160],
                    "now": now,
                },
            )
            await session.execute(
                text("""
                    INSERT INTO contacts (id, organization_id, prospect_id, display_name, role_label, provenance_id, created_at, updated_at)
                    VALUES (:id, :organization_id, :prospect_id, :name, NULL, :provenance_id, :now, :now)
                """),
                {
                    **record,
                    "id": contact_id,
                    "prospect_id": prospect_id,
                    "name": fields.full_name,
                    "provenance_id": provenance_id,
                    "now": now,
                },
            )
            for channel_type, raw_value, permitted, permission_status in (
                ("email", fields.email, bool(record["allow_email"]), str(record["email_permission_status"])),
                ("phone", fields.phone, bool(record["allow_phone"]), str(record["phone_permission_status"])),
            ):
                normalized = _normalize_channel(channel_type, raw_value) if permitted and raw_value else None
                if normalized is None or await _is_restricted(session, channel_type, normalized):
                    continue
                channel_id = uuid4()
                await session.execute(
                    text("""
                        INSERT INTO contact_channels (
                            id, organization_id, prospect_id, contact_id, channel_type, value, value_normalized,
                            provenance_id, purpose, obtained_at, verified_at, created_by
                        ) VALUES (
                            :id, :organization_id, NULL, :contact_id, :channel_type, :value, :normalized,
                            :provenance_id, :purpose, :now, :now, :actor_id
                        )
                    """),
                    {
                        **record,
                        "id": channel_id,
                        "contact_id": contact_id,
                        "channel_type": channel_type,
                        "value": raw_value,
                        "normalized": normalized,
                        "provenance_id": provenance_id,
                        "now": now,
                    },
                )
                await session.execute(
                    text("""
                        INSERT INTO contact_permissions (
                            id, organization_id, channel_id, status, legal_basis_code, provenance_id,
                            reason, decided_at, decided_by, valid_from, created_at, updated_at
                        ) VALUES (
                            :id, :organization_id, :channel_id, :status, :basis, :provenance_id,
                            NULL, :now, :actor_id, :now, :now, :now
                        )
                    """),
                    {
                        **record,
                        "id": uuid4(),
                        "channel_id": channel_id,
                        "status": permission_status,
                        "basis": "consent" if permission_status == "allowed" else None,
                        "provenance_id": provenance_id,
                        "now": now,
                    },
                )
            await _outcome(session, record, "imported", prospect_id, contact_id, provenance_id)
            await _terminal(session, ingestion_id, "succeeded", None)
            return "imported"

    async def _authorized_ingestion(self, session: AsyncSession, ingestion_id: UUID) -> Mapping[str, object] | None:
        row = (
            (
                await session.execute(
                    text("""
                    SELECT i.id, i.organization_id, i.status, i.source_occurred_at,
                           pgp_sym_decrypt(i.lead_reference_ciphertext, :encryption_key) AS lead_reference,
                           b.id AS binding_id, b.allow_full_name, b.allow_email, b.allow_phone,
                           b.email_permission_status, b.phone_permission_status,
                           c.provider_id, c.evidence_ref, a.id AS acquisition_id, a.source_label,
                           a.purpose, a.territory, i.actor_user_id AS actor_id
                    FROM connector_ingestions i
                    JOIN provider_connector_bindings b ON b.id = i.binding_id AND b.organization_id = i.organization_id
                    JOIN provider_connector_contracts c ON c.id = b.contract_id AND c.organization_id = b.organization_id
                    JOIN source_providers p ON p.id = c.provider_id AND p.organization_id = c.organization_id
                    JOIN acquisition_records a ON a.id = b.acquisition_id AND a.organization_id = b.organization_id
                    JOIN memberships m ON m.id = i.actor_membership_id AND m.organization_id = i.organization_id
                    JOIN users u ON u.id = i.actor_user_id
                    WHERE i.id = :id
                      AND b.status = 'active' AND c.status = 'approved' AND a.status = 'approved'
                      AND p.status = 'active' AND p.rights_attested_at IS NOT NULL
                      AND (p.valid_from IS NULL OR p.valid_from <= clock_timestamp())
                      AND (p.valid_until IS NULL OR p.valid_until > clock_timestamp())
                      AND (c.review_valid_until IS NULL OR c.review_valid_until > clock_timestamp())
                      AND m.status = 'active' AND u.status = 'active'
                    FOR UPDATE OF i
                """),
                    {"id": ingestion_id, "encryption_key": self._settings.meta_lead_reference_encryption_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return dict(row) if row is not None else None


class MetaLeadWebhookService:
    """Admits a signed Meta notification without retaining its payload."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self._sessions = session_factory
        self._settings = settings
        self._queue = PostgresJobQueue(session_factory)

    def verify_challenge(self, mode: str | None, token: str | None, challenge: str | None) -> str | None:
        if not self._settings.meta_lead_ads_enabled or mode != "subscribe" or challenge is None:
            return None
        return challenge if hmac.compare_digest(token or "", self._settings.meta_webhook_verify_token) else None

    async def admit(self, raw_body: bytes, signature: str | None) -> MetaWebhookAdmission:
        if not self._settings.meta_lead_ads_enabled or len(raw_body) > 65_536:
            raise MetaWebhookRejected
        expected = (
            "sha256=" + hmac.new(self._settings.meta_webhook_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        )
        if not signature or not hmac.compare_digest(signature, expected):
            raise MetaWebhookRejected
        form_id, lead_id, occurred_at = _lead_notification(raw_body)
        form_fingerprint = _fingerprint(self._settings.meta_reference_hmac_key, form_id)
        lead_fingerprint = _fingerprint(self._settings.meta_reference_hmac_key, lead_id)
        async with self._sessions.begin() as session:
            binding = (
                (
                    await session.execute(
                        text("SELECT * FROM app_private.resolve_meta_lead_binding(:fingerprint)"),
                        {"fingerprint": form_fingerprint},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if binding is None:
                raise MetaWebhookRejected
            context = TenantContext(binding["actor_user_id"], binding["organization_id"], f"meta-{uuid4().hex}")
            await _set_tenant(session, context)
            ingestion_id = uuid4()
            inserted = (
                await session.execute(
                    text("""
                        INSERT INTO connector_ingestions (
                            id, organization_id, binding_id, lead_fingerprint, lead_reference_ciphertext,
                            actor_user_id, actor_membership_id, received_at, source_occurred_at,
                            status, created_at, updated_at
                        ) VALUES (
                            :id, :organization_id, :binding_id, :lead_fingerprint,
                            pgp_sym_encrypt(:lead_id, :encryption_key, 'cipher-algo=aes256'),
                            :actor_user_id, :actor_membership_id, clock_timestamp(), :occurred_at,
                            'queued', clock_timestamp(), clock_timestamp()
                        )
                        ON CONFLICT (organization_id, binding_id, lead_fingerprint) DO NOTHING
                        RETURNING id
                    """),
                    {
                        "id": ingestion_id,
                        "organization_id": context.organization_id,
                        "binding_id": binding["binding_id"],
                        "lead_fingerprint": lead_fingerprint,
                        "lead_id": lead_id,
                        "encryption_key": self._settings.meta_lead_reference_encryption_key,
                        "actor_user_id": context.actor_id,
                        "actor_membership_id": binding["actor_membership_id"],
                        "occurred_at": occurred_at,
                    },
                )
            ).scalar_one_or_none()
            if inserted is None:
                existing = await session.scalar(
                    text(
                        "SELECT id FROM connector_ingestions WHERE binding_id = :binding AND lead_fingerprint = :lead"
                    ),
                    {"binding": binding["binding_id"], "lead": lead_fingerprint},
                )
                if not isinstance(existing, UUID):
                    raise RuntimeError("Ingestion idempotente introuvable.")
                return MetaWebhookAdmission(existing, True)
            job_id = await self._queue.enqueue(
                session,
                context=context,
                job_type="meta_lead_ads_ingest",
                schema_version=1,
                subject_type="connector_ingestion",
                subject_id=ingestion_id,
                actor_membership_id=binding["actor_membership_id"],
                idempotency_key=lead_fingerprint,
                fingerprint=hashlib.sha256(f"meta:{binding['binding_id']}:{lead_fingerprint}".encode()).hexdigest(),
                hmac_secrets={1: self._settings.job_idempotency_hmac_key.encode()},
                active_secret_version=1,
            )
            await session.execute(
                text("UPDATE connector_ingestions SET job_id = :job_id WHERE id = :id"),
                {"job_id": job_id, "id": ingestion_id},
            )
        return MetaWebhookAdmission(ingestion_id, False)


def _fingerprint(key: str, value: str) -> str:
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


async def _terminal(session: AsyncSession, ingestion_id: UUID, status: str, error_code: str | None) -> None:
    await session.execute(
        text("""
            UPDATE connector_ingestions
            SET status = :status, error_code = :error_code, finished_at = clock_timestamp(),
                updated_at = clock_timestamp(), version = version + 1
            WHERE id = :id AND status IN ('queued', 'running')
        """),
        {"id": ingestion_id, "status": status, "error_code": error_code},
    )


async def _outcome(
    session: AsyncSession,
    record: Mapping[str, object],
    result_code: str,
    prospect_id: UUID | None = None,
    contact_id: UUID | None = None,
    provenance_id: UUID | None = None,
) -> None:
    await session.execute(
        text("""
            INSERT INTO connector_ingestion_outcomes (
                id, organization_id, ingestion_id, prospect_id, contact_id, provenance_id, result_code, created_at
            ) VALUES (:id, :organization_id, :ingestion_id, :prospect_id, :contact_id, :provenance_id, :result_code, clock_timestamp())
            ON CONFLICT (organization_id, ingestion_id) DO NOTHING
        """),
        {
            "id": uuid4(),
            "organization_id": record["organization_id"],
            "ingestion_id": record["id"],
            "prospect_id": prospect_id,
            "contact_id": contact_id,
            "provenance_id": provenance_id,
            "result_code": result_code,
        },
    )


async def _is_restricted(session: AsyncSession, channel_type: str, normalized: str) -> bool:
    restricted = await session.scalar(
        text("""
            SELECT 1
            FROM contact_channels c
            JOIN contact_permissions p ON p.channel_id = c.id AND p.organization_id = c.organization_id
            WHERE c.channel_type = :channel_type AND c.value_normalized = :normalized
              AND c.archived_at IS NULL AND p.status IN ('opted_out', 'do_not_contact')
            LIMIT 1
        """),
        {"channel_type": channel_type, "normalized": normalized},
    )
    return restricted is not None


def _approved_meta_fields(payload: object) -> MetaLeadFields:
    if not isinstance(payload, dict) or not isinstance(payload.get("field_data"), list):
        raise ValueError("invalid_meta_payload")
    values: dict[str, str] = {}
    for field in payload["field_data"]:
        if not isinstance(field, dict) or field.get("name") not in {"full_name", "email", "phone"}:
            continue
        raw = field.get("values")
        if isinstance(raw, list) and raw and isinstance(raw[0], str):
            value = " ".join(raw[0].split())
            if value and len(value) <= 512:
                values[str(field["name"])] = value
    return MetaLeadFields(values.get("full_name"), values.get("email"), values.get("phone"))


def _normalize_channel(channel_type: str, value: str) -> str | None:
    if channel_type == "email":
        local, separator, domain = value.rpartition("@")
        if not separator or not local or not domain:
            return None
        try:
            normalized = f"{local.casefold()}@{domain.encode('idna').decode('ascii').casefold()}"
        except UnicodeError:
            return None
        return normalized if re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,253}", normalized, re.ASCII) else None
    normalized = re.sub(r"[\s().-]", "", value)
    return normalized if re.fullmatch(r"\+[1-9][0-9]{7,14}", normalized) else None


def _lead_notification(raw_body: bytes) -> tuple[str, str, datetime | None]:
    try:
        value = json.loads(raw_body)["entry"][0]["changes"][0]["value"]
        form_id, lead_id = str(value["form_id"]), str(value["leadgen_id"])
        occurred = value.get("created_time")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise MetaWebhookRejected from error
    if not form_id or not lead_id or len(form_id) > 128 or len(lead_id) > 128:
        raise MetaWebhookRejected
    occurred_at: datetime | None = None
    if occurred is not None:
        try:
            occurred_at = datetime.fromtimestamp(int(occurred), tz=UTC)
        except (OverflowError, TypeError, ValueError) as error:
            raise MetaWebhookRejected from error
        if occurred_at > datetime.now(UTC).replace(microsecond=0):
            raise MetaWebhookRejected
    return form_id, lead_id, occurred_at
