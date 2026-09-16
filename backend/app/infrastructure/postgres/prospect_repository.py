from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.ports.prospect import (
    AcquisitionRepository,
    ContactChannelRepository,
    ContactPermissionRepository,
    ContactRepository,
    ProspectRepository,
    ProvenanceRepository,
    SourceProviderRepository,
)
from ...domain.prospect import (
    AcquisitionDraft,
    AcquisitionRecordView,
    AcquisitionStatus,
    ArchiveReasonCode,
    ContactChannelDraft,
    ContactChannelType,
    ContactChannelView,
    ContactDraft,
    ContactPermissionStatus,
    ContactPermissionView,
    ContactView,
    ImportDeclarationDraft,
    ImportDeclarationStatus,
    ImportDeclarationView,
    ProspectDraft,
    ProspectOrigin,
    ProspectProfilePatch,
    ProspectStageCode,
    ProspectView,
    ProvenanceDraft,
    ProvenanceSourceKind,
    ProvenanceView,
    RetentionHoldDraft,
    RetentionHoldReasonCode,
    RetentionHoldReleaseReasonCode,
    RetentionHoldView,
    RetentionPolicyDraft,
    RetentionPolicyPatch,
    RetentionPolicyStatus,
    RetentionPolicyView,
    RetentionResourceType,
    RetentionReviewState,
    RetentionReviewView,
    SourceProviderDraft,
    SourceProviderPatch,
    SourceProviderStatus,
    SourceProviderView,
    ensure_channel_provenance_is_allowed,
)


class SqlAlchemySourceProviderRepository(SourceProviderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: SourceProviderDraft, *, now: datetime) -> SourceProviderView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.source_providers (
                            id, organization_id, source_kind, label, status,
                            terms_reference, terms_url, valid_from, valid_until,
                            allowed_territories, allowed_purposes, allowed_data_categories,
                            rights_attested_at, rights_attested_by, created_at, updated_at
                        )
                        VALUES (
                            :id, :organization_id, :source_kind, :label, :status,
                            :terms_reference, :terms_url, :valid_from, :valid_until,
                            CAST(:allowed_territories AS jsonb), CAST(:allowed_purposes AS jsonb),
                            CAST(:allowed_data_categories AS jsonb), :rights_attested_at,
                            :rights_attested_by, :now, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "source_kind": draft.source_kind.value,
                        "label": draft.label.strip(),
                        "status": draft.status.value,
                        "terms_reference": draft.terms_reference,
                        "terms_url": draft.terms_url,
                        "valid_from": draft.valid_from,
                        "valid_until": draft.valid_until,
                        "allowed_territories": _json_array(draft.allowed_territories),
                        "allowed_purposes": _json_array(draft.allowed_purposes),
                        "allowed_data_categories": _json_array(draft.allowed_data_categories),
                        "rights_attested_at": draft.rights_attested_at,
                        "rights_attested_by": draft.rights_attested_by,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _provider_from_row(cast(Mapping[str, object], row))

    async def get(self, provider_id: UUID) -> SourceProviderView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.source_providers WHERE id = :provider_id"),
                    {"provider_id": provider_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _provider_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def list_active(self, *, limit: int, offset: int = 0) -> tuple[SourceProviderView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.source_providers
                        ORDER BY created_at DESC, id DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_provider_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def update(
        self, provider_id: UUID, patch: SourceProviderPatch, *, now: datetime
    ) -> SourceProviderView | None:
        rights_attested_at = now if patch.rights_attested is True else None
        rights_attested_by_clause = (
            "rights_attested_at = :rights_attested_at,"
            if patch.rights_attested is not None
            else "rights_attested_at = rights_attested_at,"
        )
        rights_attested_by_value = (
            "rights_attested_by = app_private.current_actor_id(),"
            if patch.rights_attested is True
            else (
                "rights_attested_by = NULL,"
                if patch.rights_attested is False
                else "rights_attested_by = rights_attested_by,"
            )
        )
        row = (
            (
                await self._session.execute(
                    text(
                        f"""
                        UPDATE public.source_providers
                        SET label = COALESCE(:label, label),
                            status = COALESCE(:status, status),
                            terms_reference = COALESCE(:terms_reference, terms_reference),
                            terms_url = COALESCE(:terms_url, terms_url),
                            valid_from = COALESCE(:valid_from, valid_from),
                            valid_until = COALESCE(:valid_until, valid_until),
                            allowed_territories = COALESCE(CAST(:allowed_territories AS jsonb), allowed_territories),
                            allowed_purposes = COALESCE(CAST(:allowed_purposes AS jsonb), allowed_purposes),
                            allowed_data_categories =
                                COALESCE(CAST(:allowed_data_categories AS jsonb), allowed_data_categories),
                            {rights_attested_by_clause}
                            {rights_attested_by_value}
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :provider_id AND version = :version
                        RETURNING *
                        """
                    ),
                    {
                        "provider_id": provider_id,
                        "version": patch.version,
                        "label": patch.label.strip() if patch.label else None,
                        "status": patch.status.value if patch.status else None,
                        "terms_reference": patch.terms_reference,
                        "terms_url": patch.terms_url,
                        "valid_from": patch.valid_from,
                        "valid_until": patch.valid_until,
                        "allowed_territories": _optional_json_array(patch.allowed_territories),
                        "allowed_purposes": _optional_json_array(patch.allowed_purposes),
                        "allowed_data_categories": _optional_json_array(patch.allowed_data_categories),
                        "rights_attested_at": rights_attested_at,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _provider_from_row(cast(Mapping[str, object], row)) if row is not None else None


class SqlAlchemyAcquisitionRepository(AcquisitionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        draft: AcquisitionDraft,
        *,
        now: datetime,
        status: str,
        decision_reason_code: str | None = None,
        decided_by: UUID | None = None,
    ) -> AcquisitionRecordView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.acquisition_records (
                            id, organization_id, source_kind, source_label, provider_id, purpose,
                            territory, obtained_at, declared_by, status, external_reference,
                            data_categories, decision_reason_code, decided_at, decided_by,
                            declaration_idempotency_key, declaration_fingerprint,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, :organization_id, :source_kind, :source_label, :provider_id, :purpose,
                            :territory, :obtained_at, :declared_by, :status, :external_reference,
                            CAST(:data_categories AS jsonb), :decision_reason_code, :decided_at, :decided_by,
                            :declaration_idempotency_key, :declaration_fingerprint, :now, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "source_kind": draft.source_kind.value,
                        "source_label": draft.source_label.strip(),
                        "provider_id": draft.provider_id,
                        "purpose": draft.purpose,
                        "territory": draft.territory,
                        "obtained_at": draft.obtained_at,
                        "declared_by": draft.declared_by,
                        "status": status,
                        "external_reference": draft.external_reference,
                        "data_categories": _json_array(draft.data_categories),
                        "decision_reason_code": decision_reason_code,
                        "decided_at": now if decided_by is not None else None,
                        "decided_by": decided_by,
                        "declaration_idempotency_key": draft.idempotency_key,
                        "declaration_fingerprint": draft.command_fingerprint,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _acquisition_from_row(cast(Mapping[str, object], row))

    async def get(self, acquisition_id: UUID) -> AcquisitionRecordView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.acquisition_records WHERE id = :acquisition_id"),
                    {"acquisition_id": acquisition_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _acquisition_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> AcquisitionRecordView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.acquisition_records
                        WHERE declaration_idempotency_key = :idempotency_key
                        """
                    ),
                    {"idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _acquisition_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def list_recent(self, *, limit: int, offset: int = 0) -> tuple[AcquisitionRecordView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.acquisition_records
                        ORDER BY created_at DESC, id DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_acquisition_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def decide(
        self,
        acquisition_id: UUID,
        *,
        expected_version: int,
        status: str,
        now: datetime,
        decided_by: UUID,
        decision_reason_code: str | None = None,
    ) -> AcquisitionRecordView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.acquisition_records
                        SET status = :status,
                            decision_reason_code = :decision_reason_code,
                            decided_at = :now,
                            decided_by = :decided_by,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :acquisition_id AND version = :expected_version
                        RETURNING *
                        """
                    ),
                    {
                        "acquisition_id": acquisition_id,
                        "expected_version": expected_version,
                        "status": status,
                        "decision_reason_code": decision_reason_code,
                        "now": now,
                        "decided_by": decided_by,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _acquisition_from_row(cast(Mapping[str, object], row)) if row is not None else None


class SqlAlchemyProspectRepository(ProspectRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: ProspectDraft, *, now: datetime) -> ProspectView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.prospects (
                            id, organization_id, google_place_id, internal_alias, origin, source_label,
                            acquisition_record_id, owner_id, stage_code, priority,
                            retention_review_at, created_at, updated_at
                        )
                        VALUES (
                            :id, :organization_id, :google_place_id, :internal_alias, :origin, :source_label,
                            :acquisition_record_id, :owner_id, :stage_code, :priority,
                            :retention_review_at, :now, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "google_place_id": draft.google_place_id,
                        "internal_alias": draft.internal_alias.strip(),
                        "origin": draft.origin.value,
                        "source_label": draft.source_label.strip(),
                        "acquisition_record_id": draft.acquisition_record_id,
                        "owner_id": draft.owner_id,
                        "stage_code": draft.stage_code.value,
                        "priority": draft.priority,
                        "retention_review_at": draft.retention_review_at,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _prospect_from_row(cast(Mapping[str, object], row))

    async def get(self, prospect_id: UUID) -> ProspectView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.prospects WHERE id = :prospect_id"),
                    {"prospect_id": prospect_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _prospect_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def change_stage(
        self,
        prospect_id: UUID,
        *,
        expected_version: int,
        from_stage: str,
        to_stage: str,
        now: datetime,
    ) -> ProspectView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                    UPDATE public.prospects
                    SET stage_code = :to_stage, stage_changed_at = :now, updated_at = :now, version = version + 1
                    WHERE id = :prospect_id AND version = :expected_version
                      AND stage_code = :from_stage AND archived_at IS NULL
                    RETURNING *
                    """
                    ),
                    {
                        "prospect_id": prospect_id,
                        "expected_version": expected_version,
                        "from_stage": from_stage,
                        "to_stage": to_stage,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _prospect_from_row(cast(Mapping[str, object], row)) if row else None

    async def get_by_google_place_id(self, google_place_id: str) -> ProspectView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.prospects
                        WHERE google_place_id = :google_place_id AND archived_at IS NULL
                        """
                    ),
                    {"google_place_id": google_place_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _prospect_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def list_active(
        self,
        *,
        limit: int,
        after_created_at: datetime | None = None,
        after_id: UUID | None = None,
        offset: int = 0,
        include_archived: bool = False,
        search_text: str | None = None,
        origin: str | None = None,
        owner_id: UUID | None = None,
        priority: int | None = None,
        stage_code: str | None = None,
    ) -> tuple[ProspectView, ...]:
        cursor_clause = ""
        parameters: dict[str, object] = {
            "limit": limit,
            "offset": offset,
            "include_archived": include_archived,
            "search_text": f"%{search_text.strip()}%" if search_text else None,
            "origin": origin,
            "owner_id": owner_id,
            "priority": priority,
            "stage_code": stage_code,
        }
        if after_created_at is not None and after_id is not None:
            cursor_clause = "AND (created_at, id) < (:after_created_at, :after_id)"
            parameters["after_created_at"] = after_created_at
            parameters["after_id"] = after_id
        rows = (
            (
                await self._session.execute(
                    text(_active_prospect_query(cursor_clause)),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        return tuple(_prospect_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def update(
        self,
        prospect_id: UUID,
        *,
        expected_version: int,
        patch: ProspectProfilePatch,
        profile_provenance_id: UUID,
        now: datetime,
    ) -> ProspectView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.prospects
                        SET internal_alias = COALESCE(:internal_alias, internal_alias),
                            industry_label = COALESCE(:industry_label, industry_label),
                            segment_code = COALESCE(:segment_code, segment_code),
                            size_band = COALESCE(:size_band, size_band),
                            address_line_1 = COALESCE(:address_line_1, address_line_1),
                            address_line_2 = COALESCE(:address_line_2, address_line_2),
                            city = COALESCE(:city, city),
                            region = COALESCE(:region, region),
                            postal_code = COALESCE(:postal_code, postal_code),
                            country_code = COALESCE(:country_code, country_code),
                            tags = COALESCE(CAST(:tags AS jsonb), tags),
                            owner_id = COALESCE(:owner_id, owner_id),
                            priority = COALESCE(:priority, priority),
                            profile_provenance_id = :profile_provenance_id,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :prospect_id
                          AND version = :expected_version
                          AND archived_at IS NULL
                        RETURNING *
                        """
                    ),
                    {
                        "prospect_id": prospect_id,
                        "expected_version": expected_version,
                        "internal_alias": patch.internal_alias.strip() if patch.internal_alias else None,
                        "industry_label": patch.industry_label.strip() if patch.industry_label else None,
                        "segment_code": patch.segment_code,
                        "size_band": patch.size_band,
                        "address_line_1": patch.address_line_1.strip() if patch.address_line_1 else None,
                        "address_line_2": patch.address_line_2.strip() if patch.address_line_2 else None,
                        "city": patch.city.strip() if patch.city else None,
                        "region": patch.region.strip() if patch.region else None,
                        "postal_code": patch.postal_code.strip() if patch.postal_code else None,
                        "country_code": patch.country_code,
                        "tags": _optional_json_array(patch.normalized_tags()),
                        "owner_id": patch.owner_id,
                        "priority": patch.priority,
                        "profile_provenance_id": profile_provenance_id,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _prospect_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def archive(self, prospect_id: UUID, *, expected_version: int, now: datetime) -> ProspectView | None:
        result = await self.archive_with_cascade(prospect_id, expected_version=expected_version, now=now)
        return result[0] if result is not None else None

    async def archive_with_cascade(
        self, prospect_id: UUID, *, expected_version: int, now: datetime, reason_code: str = "other"
    ) -> tuple[ProspectView, int, int] | None:
        channels_result = await self._session.execute(
            text(
                """
                UPDATE public.contact_channels AS channel
                SET archived_at = :now,
                    archived_by = app_private.current_actor_id(),
                    archive_reason_code = :reason_code,
                    version = channel.version + 1
                WHERE channel.archived_at IS NULL
                  AND (
                      channel.prospect_id = :prospect_id
                      OR channel.contact_id IN (
                          SELECT id FROM public.contacts WHERE prospect_id = :prospect_id
                      )
                  )
                RETURNING channel.id
                """
            ),
            {"prospect_id": prospect_id, "reason_code": reason_code, "now": now},
        )
        contacts_result = await self._session.execute(
            text(
                """
                UPDATE public.contacts AS contact
                SET archived_at = :now,
                    archived_by = app_private.current_actor_id(),
                    archive_reason_code = :reason_code,
                    updated_at = :now,
                    version = contact.version + 1
                WHERE contact.prospect_id = :prospect_id AND contact.archived_at IS NULL
                RETURNING contact.id
                """
            ),
            {"prospect_id": prospect_id, "reason_code": reason_code, "now": now},
        )
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.prospects
                        SET archived_at = :now,
                            archived_by = app_private.current_actor_id(),
                            archive_reason_code = :reason_code,
                            stage_code = 'archived',
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :prospect_id AND version = :expected_version AND archived_at IS NULL
                        RETURNING *
                        """
                    ),
                    {
                        "prospect_id": prospect_id,
                        "expected_version": expected_version,
                        "reason_code": reason_code,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return (
            _prospect_from_row(cast(Mapping[str, object], row)),
            len(contacts_result.all()),
            len(channels_result.all()),
        )


class SqlAlchemyContactRepository(ContactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: ContactDraft, *, now: datetime) -> ContactView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.contacts (
                            id, organization_id, prospect_id, display_name, role_label,
                            provenance_id, created_at, updated_at
                        )
                        VALUES (
                            :id, :organization_id, :prospect_id, :display_name, :role_label,
                            :provenance_id, :now, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "prospect_id": draft.prospect_id,
                        "display_name": draft.display_name.strip(),
                        "role_label": draft.role_label.strip() if draft.role_label else None,
                        "provenance_id": draft.provenance_id,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _contact_from_row(cast(Mapping[str, object], row))

    async def get(self, contact_id: UUID) -> ContactView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.contacts WHERE id = :contact_id"),
                    {"contact_id": contact_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _contact_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def list_for_prospect(self, prospect_id: UUID) -> tuple[ContactView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.contacts
                        WHERE prospect_id = :prospect_id AND archived_at IS NULL
                        ORDER BY created_at DESC, id DESC
                        """
                    ),
                    {"prospect_id": prospect_id},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_contact_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def archive(
        self, contact_id: UUID, *, expected_version: int, now: datetime, reason_code: str = "other"
    ) -> tuple[ContactView, int] | None:
        channels_result = await self._session.execute(
            text(
                """
                UPDATE public.contact_channels AS channel
                SET archived_at = :now,
                    archived_by = app_private.current_actor_id(),
                    archive_reason_code = :reason_code,
                    version = channel.version + 1
                WHERE channel.contact_id = :contact_id AND channel.archived_at IS NULL
                RETURNING channel.id
                """
            ),
            {"contact_id": contact_id, "reason_code": reason_code, "now": now},
        )
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.contacts
                        SET archived_at = :now,
                            archived_by = app_private.current_actor_id(),
                            archive_reason_code = :reason_code,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :contact_id AND version = :expected_version AND archived_at IS NULL
                        RETURNING *
                        """
                    ),
                    {
                        "contact_id": contact_id,
                        "expected_version": expected_version,
                        "reason_code": reason_code,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return _contact_from_row(cast(Mapping[str, object], row)), len(channels_result.all())


class SqlAlchemyContactChannelRepository(ContactChannelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: ContactChannelDraft, *, now: datetime) -> ContactChannelView:
        provenance = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT source_kind FROM public.provenance_records
                        WHERE id = :provenance_id AND organization_id = :organization_id
                        """
                    ),
                    {"provenance_id": draft.provenance_id, "organization_id": draft.organization_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if provenance is not None:
            ensure_channel_provenance_is_allowed(ProvenanceSourceKind(str(provenance["source_kind"])))

        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.contact_channels (
                            id, organization_id, prospect_id, contact_id, channel_type, value,
                            value_normalized, provenance_id, purpose, obtained_at,
                            verified_at, created_by
                        )
                        VALUES (
                            :id, :organization_id, :prospect_id, :contact_id, :channel_type, :value,
                            :value_normalized, :provenance_id, :purpose, :obtained_at,
                            :verified_at, :created_by
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "prospect_id": draft.prospect_id,
                        "contact_id": draft.contact_id,
                        "channel_type": draft.channel_type.value,
                        "value": draft.value.strip(),
                        "value_normalized": draft.value_normalized,
                        "provenance_id": draft.provenance_id,
                        "purpose": draft.purpose,
                        "obtained_at": draft.obtained_at or now,
                        "verified_at": draft.verified_at,
                        "created_by": draft.created_by,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _channel_from_row(cast(Mapping[str, object], row))

    async def get(self, channel_id: UUID) -> ContactChannelView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.contact_channels WHERE id = :channel_id"),
                    {"channel_id": channel_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _channel_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def list_for_prospect(self, prospect_id: UUID) -> tuple[ContactChannelView, ...]:
        return await self._list_for_target("prospect_id", prospect_id)

    async def list_for_contact(self, contact_id: UUID) -> tuple[ContactChannelView, ...]:
        return await self._list_for_target("contact_id", contact_id)

    async def _list_for_target(self, column: str, target_id: UUID) -> tuple[ContactChannelView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        f"""
                        SELECT * FROM public.contact_channels
                        WHERE {column} = :target_id AND archived_at IS NULL
                        ORDER BY obtained_at DESC NULLS LAST, id DESC
                        """
                    ),
                    {"target_id": target_id},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_channel_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def find_by_normalized_value(
        self,
        *,
        channel_type: str,
        value_normalized: str,
    ) -> tuple[ContactChannelView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.contact_channels
                        WHERE channel_type = :channel_type
                          AND value_normalized = :value_normalized
                          AND archived_at IS NULL
                        ORDER BY id
                        """
                    ),
                    {"channel_type": channel_type, "value_normalized": value_normalized},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_channel_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def find_duplicate(
        self,
        *,
        channel_type: str,
        value_normalized: str,
        prospect_id: UUID | None,
        contact_id: UUID | None,
    ) -> ContactChannelView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.contact_channels
                        WHERE channel_type = :channel_type
                          AND value_normalized = :value_normalized
                          AND (
                              (CAST(:prospect_id AS uuid) IS NOT NULL AND prospect_id = CAST(:prospect_id AS uuid))
                              OR (CAST(:contact_id AS uuid) IS NOT NULL AND contact_id = CAST(:contact_id AS uuid))
                          )
                          AND archived_at IS NULL
                        LIMIT 1
                        """
                    ),
                    {
                        "channel_type": channel_type,
                        "value_normalized": value_normalized,
                        "prospect_id": prospect_id,
                        "contact_id": contact_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _channel_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def archive(
        self, channel_id: UUID, *, expected_version: int, now: datetime, reason_code: str = "other"
    ) -> ContactChannelView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.contact_channels
                        SET archived_at = :now,
                            archived_by = app_private.current_actor_id(),
                            archive_reason_code = :reason_code,
                            version = version + 1
                        WHERE id = :channel_id AND version = :expected_version AND archived_at IS NULL
                        RETURNING *
                        """
                    ),
                    {
                        "channel_id": channel_id,
                        "expected_version": expected_version,
                        "reason_code": reason_code,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _channel_from_row(cast(Mapping[str, object], row)) if row is not None else None


class SqlAlchemyContactPermissionRepository(ContactPermissionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_unknown(self, channel_id: UUID, *, organization_id: UUID, now: datetime) -> ContactPermissionView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.contact_permissions (
                            id, organization_id, channel_id, status, created_at, updated_at
                        )
                        VALUES (:id, :organization_id, :channel_id, 'unknown', :now, :now)
                        ON CONFLICT (organization_id, channel_id) DO UPDATE
                        SET updated_at = public.contact_permissions.updated_at
                        RETURNING *
                        """
                    ),
                    {"id": uuid4(), "organization_id": organization_id, "channel_id": channel_id, "now": now},
                )
            )
            .mappings()
            .one()
        )
        return _permission_from_row(cast(Mapping[str, object], row))

    async def get_by_channel(self, channel_id: UUID) -> ContactPermissionView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.contact_permissions WHERE channel_id = :channel_id"),
                    {"channel_id": channel_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _permission_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def update(
        self,
        permission_id: UUID,
        *,
        expected_version: int,
        status: ContactPermissionStatus,
        now: datetime,
        decided_by: UUID,
        legal_basis_code: str | None = None,
        provenance_id: UUID | None = None,
        reason: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> ContactPermissionView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.contact_permissions
                        SET status = :status,
                            legal_basis_code = :legal_basis_code,
                            provenance_id = :provenance_id,
                            reason = :reason,
                            decided_at = :now,
                            decided_by = :decided_by,
                            valid_from = :valid_from,
                            valid_until = :valid_until,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :permission_id AND version = :expected_version
                        RETURNING *
                        """
                    ),
                    {
                        "permission_id": permission_id,
                        "expected_version": expected_version,
                        "status": status.value,
                        "legal_basis_code": legal_basis_code,
                        "provenance_id": provenance_id,
                        "reason": reason,
                        "now": now,
                        "decided_by": decided_by,
                        "valid_from": valid_from,
                        "valid_until": valid_until,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _permission_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def apply_restriction_to_value(
        self,
        *,
        channel_type: str,
        value_normalized: str,
        status: ContactPermissionStatus,
        now: datetime,
        decided_by: UUID,
        reason: str | None,
    ) -> int:
        result = await self._session.execute(
            text(
                """
                UPDATE public.contact_permissions AS permissions
                SET status = :status,
                    legal_basis_code = NULL,
                    provenance_id = NULL,
                    reason = :reason,
                    decided_at = :now,
                    decided_by = :decided_by,
                    valid_from = NULL,
                    valid_until = NULL,
                    updated_at = :now,
                    version = permissions.version + 1
                FROM public.contact_channels AS channels
                WHERE permissions.organization_id = channels.organization_id
                  AND permissions.channel_id = channels.id
                  AND channels.channel_type = :channel_type
                  AND channels.value_normalized = :value_normalized
                  AND channels.archived_at IS NULL
                  AND permissions.status <> :status
                RETURNING permissions.id
                """
            ),
            {
                "status": status.value,
                "reason": reason,
                "now": now,
                "decided_by": decided_by,
                "channel_type": channel_type,
                "value_normalized": value_normalized,
            },
        )
        return len(result.all())


class SqlAlchemyProvenanceRepository(ProvenanceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: ProvenanceDraft, *, now: datetime) -> ProvenanceView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.provenance_records (
                            id, organization_id, source_kind, source_label, provider_id,
                            evidence_ref, purpose, territory, obtained_at, verified_at,
                            attested_by, acquisition_record_id, created_at
                        )
                        VALUES (
                            :id, :organization_id, :source_kind, :source_label, :provider_id,
                            :evidence_ref, :purpose, :territory, :obtained_at, :verified_at,
                            :attested_by, :acquisition_record_id, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "source_kind": draft.source_kind.value,
                        "source_label": draft.source_label.strip(),
                        "provider_id": draft.provider_id,
                        "evidence_ref": draft.evidence_ref,
                        "purpose": draft.purpose,
                        "territory": draft.territory,
                        "obtained_at": draft.obtained_at,
                        "verified_at": draft.verified_at,
                        "attested_by": draft.attested_by,
                        "acquisition_record_id": draft.acquisition_record_id,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _provenance_from_row(cast(Mapping[str, object], row))

    async def get(self, provenance_id: UUID) -> ProvenanceView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.provenance_records WHERE id = :provenance_id"),
                    {"provenance_id": provenance_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _provenance_from_row(cast(Mapping[str, object], row)) if row is not None else None


class SqlAlchemyRetentionPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: RetentionPolicyDraft, *, now: datetime) -> RetentionPolicyView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.retention_policies (
                            id, organization_id, resource_type, policy_code, label, status,
                            review_after_days, archive_after_days, effective_from, created_by,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, :organization_id, :resource_type, :policy_code, :label, 'draft',
                            :review_after_days, :archive_after_days, :effective_from, :created_by,
                            :now, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "resource_type": draft.resource_type.value,
                        "policy_code": draft.policy_code.strip(),
                        "label": draft.label.strip(),
                        "review_after_days": draft.review_after_days,
                        "archive_after_days": draft.archive_after_days,
                        "effective_from": draft.effective_from or now,
                        "created_by": draft.created_by,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _retention_policy_from_row(cast(Mapping[str, object], row))

    async def get(self, policy_id: UUID) -> RetentionPolicyView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.retention_policies WHERE id = :policy_id"),
                    {"policy_id": policy_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _retention_policy_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def list(
        self,
        *,
        resource_type: RetentionResourceType | None = None,
        status: RetentionPolicyStatus | None = None,
        limit: int,
        offset: int = 0,
    ) -> tuple[RetentionPolicyView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.retention_policies
                        WHERE (CAST(:resource_type AS text) IS NULL OR resource_type = CAST(:resource_type AS text))
                          AND (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
                        ORDER BY created_at DESC, id DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {
                        "resource_type": resource_type.value if resource_type else None,
                        "status": status.value if status else None,
                        "limit": limit,
                        "offset": offset,
                    },
                )
            )
            .mappings()
            .all()
        )
        return tuple(_retention_policy_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def update(
        self, policy_id: UUID, patch: RetentionPolicyPatch, *, now: datetime
    ) -> RetentionPolicyView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.retention_policies
                        SET policy_code = COALESCE(:policy_code, policy_code),
                            label = COALESCE(:label, label),
                            review_after_days = COALESCE(:review_after_days, review_after_days),
                            archive_after_days = COALESCE(:archive_after_days, archive_after_days),
                            effective_from = COALESCE(:effective_from, effective_from),
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :policy_id AND version = :version AND status = 'draft'
                        RETURNING *
                        """
                    ),
                    {
                        "policy_id": policy_id,
                        "version": patch.version,
                        "policy_code": patch.policy_code,
                        "label": patch.label,
                        "review_after_days": patch.review_after_days,
                        "archive_after_days": patch.archive_after_days,
                        "effective_from": patch.effective_from,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _retention_policy_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def activate(
        self, policy_id: UUID, *, expected_version: int, now: datetime, approved_by: UUID
    ) -> RetentionPolicyView | None:
        policy = await self.get(policy_id)
        if policy is None or policy.status is not RetentionPolicyStatus.DRAFT or policy.version != expected_version:
            return None
        await self._session.execute(
            text(
                """
                UPDATE public.retention_policies
                SET status = 'superseded',
                    effective_until = :effective_from,
                    updated_at = :now,
                    version = version + 1
                WHERE resource_type = :resource_type
                  AND status = 'active'
                  AND id <> :policy_id
                """
            ),
            {
                "policy_id": policy_id,
                "resource_type": policy.resource_type.value,
                "effective_from": policy.effective_from,
                "now": now,
            },
        )
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.retention_policies
                        SET status = 'active',
                            approved_at = :now,
                            approved_by = :approved_by,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :policy_id AND status = 'draft' AND version = :expected_version
                        RETURNING *
                        """
                    ),
                    {
                        "policy_id": policy_id,
                        "expected_version": expected_version,
                        "approved_by": approved_by,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _retention_policy_from_row(cast(Mapping[str, object], row)) if row is not None else None


class SqlAlchemyRetentionReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self,
        *,
        resource_type: RetentionResourceType | None,
        review_state: RetentionReviewState | None,
        due_before: datetime | None,
        limit: int,
        offset: int = 0,
    ) -> tuple[RetentionReviewView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(_retention_review_query()),
                    {
                        "resource_type": resource_type.value if resource_type else None,
                        "review_state": review_state.value if review_state else None,
                        "due_before": due_before,
                        "limit": limit,
                        "offset": offset,
                    },
                )
            )
            .mappings()
            .all()
        )
        return tuple(_retention_review_from_row(cast(Mapping[str, object], row)) for row in rows)


class SqlAlchemyRetentionHoldRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: RetentionHoldDraft, *, now: datetime) -> RetentionHoldView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.retention_holds (
                            id, organization_id, resource_type, resource_id, reason_code, note,
                            placed_at, placed_by, idempotency_key, command_fingerprint,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, :organization_id, :resource_type, :resource_id, :reason_code, :note,
                            :now, :placed_by, :idempotency_key, :command_fingerprint, :now, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "resource_type": draft.resource_type.value,
                        "resource_id": draft.resource_id,
                        "reason_code": draft.reason_code.value,
                        "note": draft.note.strip() if draft.note else None,
                        "placed_by": draft.placed_by,
                        "idempotency_key": draft.idempotency_key,
                        "command_fingerprint": draft.command_fingerprint,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _retention_hold_from_row(cast(Mapping[str, object], row))

    async def get(self, hold_id: UUID) -> RetentionHoldView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.retention_holds WHERE id = :hold_id"),
                    {"hold_id": hold_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _retention_hold_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> RetentionHoldView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.retention_holds WHERE idempotency_key = :idempotency_key"),
                    {"idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _retention_hold_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def has_active_hold(self, resource_type: RetentionResourceType, resource_id: UUID) -> bool:
        count = await self._session.scalar(
            text(
                """
                SELECT count(*) FROM public.retention_holds
                WHERE resource_type = :resource_type AND resource_id = :resource_id AND released_at IS NULL
                """
            ),
            {"resource_type": resource_type.value, "resource_id": resource_id},
        )
        return int(count or 0) > 0

    async def list(
        self,
        *,
        resource_type: RetentionResourceType | None = None,
        resource_id: UUID | None = None,
        active_only: bool | None = None,
        limit: int,
        offset: int = 0,
    ) -> tuple[RetentionHoldView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.retention_holds
                        WHERE (CAST(:resource_type AS text) IS NULL OR resource_type = CAST(:resource_type AS text))
                          AND (CAST(:resource_id AS uuid) IS NULL OR resource_id = CAST(:resource_id AS uuid))
                          AND (CAST(:active_only AS boolean) IS NULL OR (released_at IS NULL) = CAST(:active_only AS boolean))
                        ORDER BY placed_at DESC, id DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {
                        "resource_type": resource_type.value if resource_type else None,
                        "resource_id": resource_id,
                        "active_only": active_only,
                        "limit": limit,
                        "offset": offset,
                    },
                )
            )
            .mappings()
            .all()
        )
        return tuple(_retention_hold_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def release(
        self,
        hold_id: UUID,
        *,
        expected_version: int,
        release_reason_code: RetentionHoldReleaseReasonCode,
        released_by: UUID,
        now: datetime,
    ) -> RetentionHoldView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.retention_holds
                        SET released_at = :now,
                            released_by = :released_by,
                            release_reason_code = :release_reason_code,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :hold_id
                          AND version = :expected_version
                          AND released_at IS NULL
                        RETURNING *
                        """
                    ),
                    {
                        "hold_id": hold_id,
                        "expected_version": expected_version,
                        "release_reason_code": release_reason_code.value,
                        "released_by": released_by,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _retention_hold_from_row(cast(Mapping[str, object], row)) if row is not None else None


class SqlAlchemyImportDeclarationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        draft: ImportDeclarationDraft,
        *,
        now: datetime,
        status: str,
        decision_reason_codes: tuple[str, ...],
    ) -> ImportDeclarationView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.import_declarations (
                            id, organization_id, acquisition_record_id, declaration_label, format_code,
                            schema_code, declared_field_codes, declared_data_categories, estimated_row_count,
                            declared_content_sha256, status, decision_reason_codes, declared_by,
                            declared_at, idempotency_key, command_fingerprint, created_at, updated_at
                        )
                        VALUES (
                            :id, :organization_id, :acquisition_record_id, :declaration_label, :format_code,
                            :schema_code, CAST(:declared_field_codes AS jsonb),
                            CAST(:declared_data_categories AS jsonb), :estimated_row_count,
                            :declared_content_sha256, :status, CAST(:decision_reason_codes AS jsonb),
                            :declared_by, :now, :idempotency_key, :command_fingerprint, :now, :now
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": draft.organization_id,
                        "acquisition_record_id": draft.acquisition_record_id,
                        "declaration_label": draft.declaration_label.strip(),
                        "format_code": draft.format_code,
                        "schema_code": draft.schema_code,
                        "declared_field_codes": _json_array(draft.declared_field_codes),
                        "declared_data_categories": _json_array(draft.declared_data_categories),
                        "estimated_row_count": draft.estimated_row_count,
                        "declared_content_sha256": draft.declared_content_sha256,
                        "status": status,
                        "decision_reason_codes": _json_array(decision_reason_codes),
                        "declared_by": draft.declared_by,
                        "idempotency_key": draft.idempotency_key,
                        "command_fingerprint": draft.command_fingerprint,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _import_declaration_from_row(cast(Mapping[str, object], row))

    async def get(self, declaration_id: UUID) -> ImportDeclarationView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.import_declarations WHERE id = :declaration_id"),
                    {"declaration_id": declaration_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _import_declaration_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> ImportDeclarationView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.import_declarations WHERE idempotency_key = :idempotency_key"),
                    {"idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _import_declaration_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def list(self, *, limit: int, offset: int = 0) -> tuple[ImportDeclarationView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.import_declarations
                        ORDER BY created_at DESC, id DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_import_declaration_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def cancel(
        self, declaration_id: UUID, *, expected_version: int, now: datetime
    ) -> ImportDeclarationView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.import_declarations
                        SET status = 'cancelled',
                            cancelled_at = :now,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :declaration_id
                          AND version = :expected_version
                          AND status IN ('declared', 'quarantined')
                        RETURNING *
                        """
                    ),
                    {"declaration_id": declaration_id, "expected_version": expected_version, "now": now},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _import_declaration_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def archive(
        self, declaration_id: UUID, *, expected_version: int, archive_reason_code: str, now: datetime
    ) -> ImportDeclarationView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.import_declarations
                        SET status = 'archived',
                            archived_at = :now,
                            archived_by = app_private.current_actor_id(),
                            archive_reason_code = :archive_reason_code,
                            updated_at = :now,
                            version = version + 1
                        WHERE id = :declaration_id
                          AND version = :expected_version
                          AND status <> 'archived'
                        RETURNING *
                        """
                    ),
                    {
                        "declaration_id": declaration_id,
                        "expected_version": expected_version,
                        "archive_reason_code": archive_reason_code,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _import_declaration_from_row(cast(Mapping[str, object], row)) if row is not None else None


def _prospect_from_row(row: Mapping[str, object]) -> ProspectView:
    return ProspectView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        internal_alias=str(row["internal_alias"]),
        origin=ProspectOrigin(str(row["origin"])),
        source_label=str(row["source_label"]),
        google_place_id=_optional_str(row["google_place_id"]),
        stage_code=ProspectStageCode(str(row["stage_code"])),
        priority=int(cast(int, row["priority"])),
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        archived_at=_optional_datetime(row["archived_at"]),
        stage_changed_at=_optional_datetime(row.get("stage_changed_at")),
        owner_id=_optional_uuid(row.get("owner_id")),
        profile_provenance_id=_optional_uuid(row.get("profile_provenance_id")),
        industry_label=_optional_str(row.get("industry_label")),
        segment_code=str(row.get("segment_code") or "unspecified"),
        size_band=str(row.get("size_band") or "unknown"),
        address_line_1=_optional_str(row.get("address_line_1")),
        address_line_2=_optional_str(row.get("address_line_2")),
        city=_optional_str(row.get("city")),
        region=_optional_str(row.get("region")),
        postal_code=_optional_str(row.get("postal_code")),
        country_code=_optional_str(row.get("country_code")),
        tags=_tuple_from_json(row.get("tags")),
    )


def _contact_from_row(row: Mapping[str, object]) -> ContactView:
    return ContactView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        prospect_id=UUID(str(row["prospect_id"])),
        display_name=str(row["display_name"]),
        role_label=_optional_str(row["role_label"]),
        provenance_id=UUID(str(row["provenance_id"])),
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        archived_at=_optional_datetime(row["archived_at"]),
    )


def _channel_from_row(row: Mapping[str, object]) -> ContactChannelView:
    return ContactChannelView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        channel_type=ContactChannelType(str(row["channel_type"])),
        value=str(row["value"]),
        value_normalized=str(row["value_normalized"]),
        provenance_id=UUID(str(row["provenance_id"])),
        prospect_id=_optional_uuid(row["prospect_id"]),
        contact_id=_optional_uuid(row["contact_id"]),
        purpose=str(row["purpose"]),
        version=int(cast(int, row["version"])),
        archived_at=_optional_datetime(row["archived_at"]),
    )


def _provenance_from_row(row: Mapping[str, object]) -> ProvenanceView:
    return ProvenanceView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        source_kind=ProvenanceSourceKind(str(row["source_kind"])),
        source_label=str(row["source_label"]),
        purpose=str(row["purpose"]),
        obtained_at=_datetime(row["obtained_at"]),
        created_at=_datetime(row["created_at"]),
        provider_id=_optional_uuid(row["provider_id"]),
        acquisition_record_id=_optional_uuid(row.get("acquisition_record_id")),
    )


def _provider_from_row(row: Mapping[str, object]) -> SourceProviderView:
    return SourceProviderView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        source_kind=ProvenanceSourceKind(str(row["source_kind"])),
        label=str(row["label"]),
        status=SourceProviderStatus(str(row["status"])),
        terms_reference=_optional_str(row.get("terms_reference")),
        terms_url=_optional_str(row.get("terms_url")),
        valid_from=_optional_datetime(row.get("valid_from")),
        valid_until=_optional_datetime(row.get("valid_until")),
        allowed_territories=_tuple_from_json(row.get("allowed_territories")),
        allowed_purposes=_tuple_from_json(row.get("allowed_purposes")),
        allowed_data_categories=_tuple_from_json(row.get("allowed_data_categories")),
        rights_attested_at=_optional_datetime(row.get("rights_attested_at")),
        rights_attested_by=_optional_uuid(row.get("rights_attested_by")),
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
    )


def _acquisition_from_row(row: Mapping[str, object]) -> AcquisitionRecordView:
    return AcquisitionRecordView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        source_kind=ProvenanceSourceKind(str(row["source_kind"])),
        source_label=str(row["source_label"]),
        provider_id=UUID(str(row["provider_id"])),
        purpose=str(row["purpose"]),
        territory=str(row["territory"]),
        obtained_at=_datetime(row["obtained_at"]),
        declared_by=UUID(str(row["declared_by"])),
        data_categories=_tuple_from_json(row.get("data_categories")),
        status=AcquisitionStatus(str(row["status"])),
        decision_reason_code=_optional_str(row.get("decision_reason_code")),
        external_reference=_optional_str(row.get("external_reference")),
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        decided_at=_optional_datetime(row.get("decided_at")),
        decided_by=_optional_uuid(row.get("decided_by")),
        command_fingerprint=_optional_str(row.get("declaration_fingerprint")),
    )


def _permission_from_row(row: Mapping[str, object]) -> ContactPermissionView:
    return ContactPermissionView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        channel_id=UUID(str(row["channel_id"])),
        status=ContactPermissionStatus(str(row["status"])),
        legal_basis_code=_optional_str(row.get("legal_basis_code")),
        provenance_id=_optional_uuid(row["provenance_id"]),
        reason=_optional_str(row["reason"]),
        decided_at=_optional_datetime(row["decided_at"]),
        decided_by=_optional_uuid(row.get("decided_by")),
        valid_from=_optional_datetime(row.get("valid_from")),
        valid_until=_optional_datetime(row.get("valid_until")),
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
    )


def _retention_policy_from_row(row: Mapping[str, object]) -> RetentionPolicyView:
    return RetentionPolicyView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        resource_type=RetentionResourceType(str(row["resource_type"])),
        policy_code=str(row["policy_code"]),
        label=str(row["label"]),
        status=RetentionPolicyStatus(str(row["status"])),
        review_after_days=int(cast(int, row["review_after_days"])),
        archive_after_days=_optional_int(row.get("archive_after_days")),
        effective_from=_datetime(row["effective_from"]),
        effective_until=_optional_datetime(row.get("effective_until")),
        approved_at=_optional_datetime(row.get("approved_at")),
        approved_by=_optional_uuid(row.get("approved_by")),
        created_by=_optional_uuid(row.get("created_by")),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        version=int(cast(int, row["version"])),
    )


def _retention_review_from_row(row: Mapping[str, object]) -> RetentionReviewView:
    return RetentionReviewView(
        resource_type=RetentionResourceType(str(row["resource_type"])),
        resource_id=UUID(str(row["resource_id"])),
        reference_at=_datetime(row["reference_at"]),
        review_due_at=_optional_datetime(row.get("review_due_at")),
        review_state=RetentionReviewState(str(row["review_state"])),
        policy_id=_optional_uuid(row.get("policy_id")),
        policy_code=_optional_str(row.get("policy_code")),
        active_hold_count=int(cast(int, row["active_hold_count"])),
        archived_at=_optional_datetime(row.get("archived_at")),
    )


def _retention_hold_from_row(row: Mapping[str, object]) -> RetentionHoldView:
    release_reason = _optional_str(row.get("release_reason_code"))
    return RetentionHoldView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        resource_type=RetentionResourceType(str(row["resource_type"])),
        resource_id=UUID(str(row["resource_id"])),
        reason_code=RetentionHoldReasonCode(str(row["reason_code"])),
        note=_optional_str(row.get("note")),
        placed_at=_datetime(row["placed_at"]),
        placed_by=_optional_uuid(row.get("placed_by")),
        released_at=_optional_datetime(row.get("released_at")),
        released_by=_optional_uuid(row.get("released_by")),
        release_reason_code=RetentionHoldReleaseReasonCode(release_reason) if release_reason else None,
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        command_fingerprint=_optional_str(row.get("command_fingerprint")),
    )


def _import_declaration_from_row(row: Mapping[str, object]) -> ImportDeclarationView:
    archive_reason = _optional_str(row.get("archive_reason_code"))
    return ImportDeclarationView(
        id=UUID(str(row["id"])),
        organization_id=UUID(str(row["organization_id"])),
        acquisition_record_id=UUID(str(row["acquisition_record_id"])),
        declaration_label=str(row["declaration_label"]),
        format_code=str(row["format_code"]),
        schema_code=str(row["schema_code"]),
        declared_field_codes=_tuple_from_json(row.get("declared_field_codes")),
        declared_data_categories=_tuple_from_json(row.get("declared_data_categories")),
        estimated_row_count=_optional_int(row.get("estimated_row_count")),
        declared_content_sha256=_optional_str(row.get("declared_content_sha256")),
        status=ImportDeclarationStatus(str(row["status"])),
        decision_reason_codes=_tuple_from_json(row.get("decision_reason_codes")),
        declared_by=_optional_uuid(row.get("declared_by")),
        declared_at=_datetime(row["declared_at"]),
        cancelled_at=_optional_datetime(row.get("cancelled_at")),
        archived_at=_optional_datetime(row.get("archived_at")),
        archived_by=_optional_uuid(row.get("archived_by")),
        archive_reason_code=ArchiveReasonCode(archive_reason) if archive_reason else None,
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
        command_fingerprint=_optional_str(row.get("command_fingerprint")),
    )


def _datetime(value: object) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(cast(int, value))


def _json_array(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=True, separators=(",", ":"))


def _optional_json_array(values: tuple[str, ...] | None) -> str | None:
    return None if values is None else _json_array(values)


def _tuple_from_json(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    decoded = json.loads(value) if isinstance(value, str) else value
    if not isinstance(decoded, list):
        return ()
    return tuple(str(item) for item in decoded)


def _active_prospect_query(cursor_clause: str) -> str:
    return f"""
        SELECT * FROM public.prospects
        WHERE (:include_archived OR archived_at IS NULL)
          AND (
              CAST(:search_text AS text) IS NULL
              OR internal_alias ILIKE CAST(:search_text AS text)
              OR google_place_id ILIKE CAST(:search_text AS text)
              OR industry_label ILIKE CAST(:search_text AS text)
              OR city ILIKE CAST(:search_text AS text)
          )
          AND (CAST(:origin AS text) IS NULL OR origin = CAST(:origin AS text))
          AND (CAST(:owner_id AS uuid) IS NULL OR owner_id = CAST(:owner_id AS uuid))
          AND (CAST(:priority AS integer) IS NULL OR priority = CAST(:priority AS integer))
          AND (CAST(:stage_code AS text) IS NULL OR stage_code = CAST(:stage_code AS text))
          {cursor_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
    """


def _retention_review_query() -> str:
    return """
        WITH resources AS (
            SELECT 'prospect'::text AS resource_type, id AS resource_id, organization_id,
                   COALESCE(retention_review_at, created_at) AS reference_at, archived_at
            FROM public.prospects
            UNION ALL
            SELECT 'contact'::text, id, organization_id, created_at, archived_at
            FROM public.contacts
            UNION ALL
            SELECT 'contact_channel'::text, id, organization_id, COALESCE(obtained_at, CURRENT_TIMESTAMP), archived_at
            FROM public.contact_channels
            UNION ALL
            SELECT 'acquisition_record'::text, id, organization_id, obtained_at, NULL::timestamptz
            FROM public.acquisition_records
            UNION ALL
            SELECT 'provenance_record'::text, id, organization_id, obtained_at, NULL::timestamptz
            FROM public.provenance_records
            UNION ALL
            SELECT 'import_declaration'::text, id, organization_id, declared_at, archived_at
            FROM public.import_declarations
        ),
        reviews AS (
            SELECT resources.resource_type,
                   resources.resource_id,
                   resources.reference_at,
                   resources.archived_at,
                   policies.id AS policy_id,
                   policies.policy_code,
                   CASE
                       WHEN policies.id IS NULL THEN NULL
                       ELSE resources.reference_at + make_interval(days => policies.review_after_days)
                   END AS review_due_at,
                   (
                       SELECT count(*)
                       FROM public.retention_holds holds
                       WHERE holds.resource_type = resources.resource_type
                         AND holds.resource_id = resources.resource_id
                         AND holds.released_at IS NULL
                   ) AS active_hold_count
            FROM resources
            LEFT JOIN LATERAL (
                SELECT *
                FROM public.retention_policies policy
                WHERE policy.resource_type = resources.resource_type
                  AND policy.status IN ('active', 'superseded')
                  AND policy.effective_from <= resources.reference_at
                  AND (policy.effective_until IS NULL OR policy.effective_until > resources.reference_at)
                ORDER BY policy.effective_from DESC, policy.created_at DESC
                LIMIT 1
            ) policies ON true
        )
        SELECT *,
               CASE
                   WHEN archived_at IS NOT NULL THEN 'archived'
                   WHEN active_hold_count > 0 THEN 'on_hold'
                   WHEN policy_id IS NULL THEN 'policy_missing'
                   WHEN review_due_at < CURRENT_TIMESTAMP THEN 'overdue'
                   WHEN review_due_at <= CURRENT_TIMESTAMP + interval '30 days' THEN 'due'
                   ELSE 'upcoming'
               END AS review_state
        FROM reviews
        WHERE (CAST(:resource_type AS text) IS NULL OR resource_type = CAST(:resource_type AS text))
          AND (CAST(:due_before AS timestamptz) IS NULL OR review_due_at <= CAST(:due_before AS timestamptz))
          AND (
              CAST(:review_state AS text) IS NULL OR
              CASE
                   WHEN archived_at IS NOT NULL THEN 'archived'
                   WHEN active_hold_count > 0 THEN 'on_hold'
                   WHEN policy_id IS NULL THEN 'policy_missing'
                   WHEN review_due_at < CURRENT_TIMESTAMP THEN 'overdue'
                   WHEN review_due_at <= CURRENT_TIMESTAMP + interval '30 days' THEN 'due'
                   ELSE 'upcoming'
              END = CAST(:review_state AS text)
          )
        ORDER BY review_due_at NULLS FIRST, resource_type, resource_id
        LIMIT :limit OFFSET :offset
    """
