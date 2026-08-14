from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.ports.prospect import (
    ContactChannelRepository,
    ContactRepository,
    ProspectRepository,
    ProvenanceRepository,
)
from ...domain.prospect import (
    ContactChannelDraft,
    ContactChannelType,
    ContactChannelView,
    ContactDraft,
    ContactView,
    ProspectDraft,
    ProspectOrigin,
    ProspectStageCode,
    ProspectView,
    ProvenanceDraft,
    ProvenanceSourceKind,
    ProvenanceView,
    ensure_channel_provenance_is_allowed,
)


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
    ) -> tuple[ProspectView, ...]:
        cursor_clause = ""
        parameters: dict[str, object] = {"limit": limit, "offset": offset}
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

    async def archive(self, prospect_id: UUID, *, expected_version: int, now: datetime) -> ProspectView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        UPDATE public.prospects
                        SET archived_at = :now, stage_code = 'archived', updated_at = :now, version = version + 1
                        WHERE id = :prospect_id AND version = :expected_version AND archived_at IS NULL
                        RETURNING *
                        """
                    ),
                    {"prospect_id": prospect_id, "expected_version": expected_version, "now": now},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _prospect_from_row(cast(Mapping[str, object], row)) if row is not None else None


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
                            attested_by, created_at
                        )
                        VALUES (
                            :id, :organization_id, :source_kind, :source_label, :provider_id,
                            :evidence_ref, :purpose, :territory, :obtained_at, :verified_at,
                            :attested_by, :now
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
    )


def _datetime(value: object) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _active_prospect_query(cursor_clause: str) -> str:
    return f"""
        SELECT * FROM public.prospects
        WHERE archived_at IS NULL
          {cursor_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
    """
