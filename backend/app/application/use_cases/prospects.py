from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC
from uuid import UUID

from ...domain.audit import AuditAction
from ...domain.prospect import ProspectDraft, ProspectOrigin, ProspectView
from ..audit_events import tenant_audit_event
from ..errors import (
    InsufficientCapability,
    InvalidGoogleSelectionGrant,
    ProspectResourceNotFound,
)
from ..models import GoogleAccessOwner
from ..ports import Clock, CursorCodec
from ..ports.prospect import GoogleSelectionGrantStore, ProspectUnitOfWorkFactory
from ..tenancy import TenantContext

GOOGLE_SOURCE_LABEL = "google_places:text_search"
MANUAL_SOURCE_LABEL = "manual:user_entry"
MAX_GOOGLE_PROSPECTS_PER_COMMAND = 20


@dataclass(frozen=True, slots=True)
class ProspectPage:
    items: tuple[ProspectView, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class GoogleProspectAddItem:
    place_id: str
    disposition: str
    prospect: ProspectView


@dataclass(frozen=True, slots=True)
class GoogleProspectAddOutcome:
    items: tuple[GoogleProspectAddItem, ...]


class CreateManualProspectUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(self, *, context: TenantContext, internal_alias: str, has_capability: bool) -> ProspectView:
        _require_capability(has_capability)
        now = self._clock.now()
        draft = ProspectDraft(
            organization_id=context.organization_id,
            internal_alias=internal_alias,
            origin=ProspectOrigin.MANUAL,
            source_label=MANUAL_SOURCE_LABEL,
        )
        async with self._unit_of_work_factory(context) as unit_of_work:
            prospect = await unit_of_work.prospects.add(draft, now=now)
            await unit_of_work.audit.record(
                tenant_audit_event(context, AuditAction.PROSPECT_CREATED, prospect.id, {"origin": "manual"})
            )
            await unit_of_work.commit()
            return prospect


class AddGoogleProspectsUseCase:
    def __init__(
        self,
        unit_of_work_factory: ProspectUnitOfWorkFactory,
        selection_grants: GoogleSelectionGrantStore,
        clock: Clock,
        *,
        alias_hmac_key: bytes,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._selection_grants = selection_grants
        self._clock = clock
        self._alias_hmac_key = alias_hmac_key

    async def execute(
        self,
        *,
        context: TenantContext,
        owner: GoogleAccessOwner,
        selection_token: str,
        place_ids: tuple[str, ...],
        has_capability: bool,
    ) -> GoogleProspectAddOutcome:
        _require_capability(has_capability)
        requested = _distinct_place_ids(place_ids)
        allowed = set(await self._selection_grants.resolve(selection_token, owner, now=self._clock.now()))
        if not requested or any(place_id not in allowed for place_id in requested):
            raise InvalidGoogleSelectionGrant

        now = self._clock.now()
        items: list[GoogleProspectAddItem] = []
        async with self._unit_of_work_factory(context) as unit_of_work:
            for place_id in requested:
                existing = await unit_of_work.prospects.get_by_google_place_id(place_id)
                if existing is not None:
                    items.append(GoogleProspectAddItem(place_id=place_id, disposition="existing", prospect=existing))
                    continue
                prospect = await unit_of_work.prospects.add(
                    ProspectDraft(
                        organization_id=context.organization_id,
                        internal_alias=_google_alias(context.organization_id, place_id, self._alias_hmac_key),
                        origin=ProspectOrigin.GOOGLE_PLACE,
                        source_label=GOOGLE_SOURCE_LABEL,
                        google_place_id=place_id,
                    ),
                    now=now,
                )
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        AuditAction.PROSPECT_CREATED,
                        prospect.id,
                        {"origin": "google_place"},
                    )
                )
                items.append(GoogleProspectAddItem(place_id=place_id, disposition="created", prospect=prospect))
            await unit_of_work.commit()
        return GoogleProspectAddOutcome(items=tuple(items))


class ListProspectsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, cursor_codec: CursorCodec) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._cursor_codec = cursor_codec

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        cursor: str | None,
        limit: int,
    ) -> ProspectPage:
        _require_capability(has_capability)
        _validate_limit(limit)
        after_created_at, after_id = self._cursor_codec.decode(cursor)
        async with self._unit_of_work_factory(context) as unit_of_work:
            rows = await unit_of_work.prospects.list_active(
                limit=limit + 1,
                after_created_at=after_created_at,
                after_id=after_id,
            )
        items = rows[:limit]
        return ProspectPage(items=items, next_cursor=_next_cursor(rows, items, limit, self._cursor_codec))


class GetProspectUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(self, *, context: TenantContext, prospect_id: UUID, has_capability: bool) -> ProspectView:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            prospect = await unit_of_work.prospects.get(prospect_id)
        if prospect is None:
            raise ProspectResourceNotFound
        return prospect


def _require_capability(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability


def _distinct_place_ids(place_ids: tuple[str, ...]) -> tuple[str, ...]:
    distinct = tuple(dict.fromkeys(place_id.strip() for place_id in place_ids if place_id.strip()))
    if not 1 <= len(distinct) <= MAX_GOOGLE_PROSPECTS_PER_COMMAND:
        raise InvalidGoogleSelectionGrant
    return distinct


def _google_alias(organization_id: UUID, place_id: str, alias_hmac_key: bytes) -> str:
    digest = (
        hmac.new(
            alias_hmac_key,
            f"{organization_id}:{place_id}".encode(),
            hashlib.sha256,
        )
        .hexdigest()[:10]
        .upper()
    )
    return f"Prospect Google {digest}"


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("limit doit etre compris entre 1 et 100.")


def _next_cursor(
    rows: tuple[ProspectView, ...],
    items: tuple[ProspectView, ...],
    limit: int,
    cursor_codec: CursorCodec,
) -> str | None:
    if len(rows) <= limit or not items:
        return None
    last = items[-1]
    created_at = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=UTC)
    return cursor_codec.encode(created_at, last.id)
