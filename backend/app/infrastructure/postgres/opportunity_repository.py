from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.ports.opportunity import OpportunityEventRepository, OpportunityRepository
from ...domain.opportunity import (
    OpportunityCurrencyAggregate,
    OpportunityDraft,
    OpportunityEventType,
    OpportunityEventView,
    OpportunityLossReasonCode,
    OpportunityProspectSummary,
    OpportunityStageCode,
    OpportunityView,
)


class SqlAlchemyOpportunityRepository(OpportunityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, draft: OpportunityDraft, *, organization_id: UUID, actor_id: UUID, now: datetime
    ) -> OpportunityView:
        if not await self.is_active_owner(draft.owner_membership_id):
            raise ValueError("Le responsable de l’opportunité doit être un membre actif de l’organisation.")
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.opportunities (
                            id, organization_id, prospect_id, owner_membership_id, name, amount, currency_code,
                            probability, stage_code, expected_close_on, created_by, created_at, updated_at
                        ) VALUES (
                            :id, :organization_id, :prospect_id, :owner_membership_id, :name, :amount, :currency_code,
                            :probability, 'discovery', :expected_close_on, :created_by, :now, :now
                        ) RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": organization_id,
                        "prospect_id": draft.prospect_id,
                        "owner_membership_id": draft.owner_membership_id,
                        "name": draft.name,
                        "amount": draft.amount,
                        "currency_code": draft.currency_code,
                        "probability": draft.probability,
                        "expected_close_on": draft.expected_close_on,
                        "created_by": actor_id,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _opportunity_from_row(cast(Mapping[str, object], row))

    async def get(self, opportunity_id: UUID) -> OpportunityView | None:
        row = (
            (
                await self._session.execute(
                    text(_opportunity_select("WHERE opportunities.id = :id")), {"id": opportunity_id}
                )
            )
            .mappings()
            .one_or_none()
        )
        return _opportunity_from_row(cast(Mapping[str, object], row)) if row else None

    async def get_for_update(self, opportunity_id: UUID) -> OpportunityView | None:
        row = (
            (
                await self._session.execute(
                    text(_opportunity_select("WHERE opportunities.id = :id FOR UPDATE OF opportunities")),
                    {"id": opportunity_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _opportunity_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[OpportunityView, ...]:
        return await self.list(prospect_id=prospect_id, limit=limit)

    async def list(
        self,
        *,
        limit: int,
        prospect_id: UUID | None = None,
        owner_membership_id: UUID | None = None,
        stage_codes: tuple[OpportunityStageCode, ...] = (),
        currency_code: str | None = None,
        search_text: str | None = None,
        expected_close_from: date | None = None,
        expected_close_to: date | None = None,
        overdue: bool | None = None,
        organization_today: date | None = None,
        after_expected_close_on: date | None = None,
        after_updated_at: datetime | None = None,
        after_id: UUID | None = None,
    ) -> tuple[OpportunityView, ...]:
        clauses, parameters = _opportunity_filters(
            prospect_id=prospect_id,
            owner_membership_id=owner_membership_id,
            stage_codes=stage_codes,
            currency_code=currency_code,
            search_text=search_text,
            expected_close_from=expected_close_from,
            expected_close_to=expected_close_to,
            overdue=overdue,
            organization_today=organization_today,
        )
        if after_expected_close_on is not None and after_updated_at is not None and after_id is not None:
            clauses.append(
                """
                (opportunities.expected_close_on > :after_expected_close_on
                 OR (opportunities.expected_close_on = :after_expected_close_on
                     AND (opportunities.updated_at < :after_updated_at
                          OR (opportunities.updated_at = :after_updated_at AND opportunities.id > :after_id))))
                """
            )
            parameters.update(
                {
                    "after_expected_close_on": after_expected_close_on,
                    "after_updated_at": after_updated_at,
                    "after_id": after_id,
                }
            )
        rows = (
            (
                await self._session.execute(
                    text(
                        _opportunity_select(
                            "WHERE "
                            + " AND ".join(clauses)
                            + " ORDER BY opportunities.expected_close_on ASC, opportunities.updated_at DESC, "
                            "opportunities.id ASC LIMIT :limit"
                        )
                    ),
                    {**parameters, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_opportunity_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def aggregate(
        self,
        *,
        prospect_id: UUID | None = None,
        owner_membership_id: UUID | None = None,
        stage_codes: tuple[OpportunityStageCode, ...] = (),
        currency_code: str | None = None,
        search_text: str | None = None,
        expected_close_from: date | None = None,
        expected_close_to: date | None = None,
        overdue: bool | None = None,
        organization_today: date,
    ) -> tuple[OpportunityCurrencyAggregate, ...]:
        clauses, parameters = _opportunity_filters(
            prospect_id=prospect_id,
            owner_membership_id=owner_membership_id,
            stage_codes=stage_codes,
            currency_code=currency_code,
            search_text=search_text,
            expected_close_from=expected_close_from,
            expected_close_to=expected_close_to,
            overdue=overdue,
            organization_today=organization_today,
        )
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT opportunities.currency_code,
                               COUNT(*) AS count,
                               COALESCE(SUM(opportunities.amount), 0) AS amount_total,
                               COALESCE(SUM(opportunities.amount * opportunities.probability / 100.0), 0)
                                   AS weighted_amount_total,
                               COUNT(*) FILTER (WHERE opportunities.stage_code IN ('discovery', 'qualification',
                                   'proposal', 'negotiation')) AS open_count,
                               COUNT(*) FILTER (WHERE opportunities.stage_code = 'won') AS won_count,
                               COUNT(*) FILTER (WHERE opportunities.stage_code = 'lost') AS lost_count,
                               COUNT(*) FILTER (WHERE opportunities.stage_code IN ('discovery', 'qualification',
                                   'proposal', 'negotiation') AND opportunities.expected_close_on < :today)
                                   AS overdue_open_count
                        FROM public.opportunities opportunities
                        JOIN public.prospects prospects ON prospects.id = opportunities.prospect_id
                        WHERE """
                        + " AND ".join(clauses)
                        + " GROUP BY opportunities.currency_code ORDER BY opportunities.currency_code ASC"
                    ),
                    {**parameters, "today": organization_today},
                )
            )
            .mappings()
            .all()
        )
        return tuple(
            OpportunityCurrencyAggregate(
                currency_code=str(row["currency_code"]).strip(),
                count=int(cast(int, row["count"])),
                amount_total=cast(Decimal, row["amount_total"]),
                weighted_amount_total=cast(Decimal, row["weighted_amount_total"]),
                open_count=int(cast(int, row["open_count"])),
                won_count=int(cast(int, row["won_count"])),
                lost_count=int(cast(int, row["lost_count"])),
                overdue_open_count=int(cast(int, row["overdue_open_count"])),
            )
            for row in rows
        )

    async def update(
        self,
        opportunity_id: UUID,
        *,
        expected_version: int,
        changes: Mapping[str, object],
        now: datetime,
    ) -> OpportunityView | None:
        allowed = {
            "owner_membership_id",
            "name",
            "amount",
            "currency_code",
            "probability",
            "stage_code",
            "expected_close_on",
            "loss_reason_code",
            "loss_reason_note",
            "closed_at",
        }
        unexpected = set(changes).difference(allowed)
        if not changes or unexpected:
            raise ValueError("Les changements d’opportunité sont invalides.")
        if "owner_membership_id" in changes:
            owner_membership_id = changes["owner_membership_id"]
            if not isinstance(owner_membership_id, UUID) or not await self.is_active_owner(owner_membership_id):
                raise ValueError("Le responsable de l’opportunité doit être un membre actif de l’organisation.")
        assignments = [f"{field} = :{field}" for field in changes]
        assignments.extend(("updated_at = :now", "version = version + 1"))
        parameters: dict[str, object] = {
            **changes,
            "id": opportunity_id,
            "expected_version": expected_version,
            "now": now,
        }
        row = (
            (
                await self._session.execute(
                    text(
                        "UPDATE public.opportunities SET "
                        + ", ".join(assignments)
                        + " WHERE id = :id AND version = :expected_version RETURNING *"
                    ),
                    parameters,
                )
            )
            .mappings()
            .one_or_none()
        )
        return _opportunity_from_row(cast(Mapping[str, object], row)) if row else None

    async def is_active_owner(self, membership_id: UUID) -> bool:
        return bool(
            (
                await self._session.execute(
                    text("SELECT EXISTS(SELECT 1 FROM public.memberships WHERE id = :id AND status = 'active')"),
                    {"id": membership_id},
                )
            ).scalar_one()
        )

    async def summaries_for_prospects(
        self,
        prospect_ids: tuple[UUID, ...],
        *,
        owner_membership_id: UUID | None,
        organization_today: date,
    ) -> tuple[OpportunityProspectSummary, ...]:
        if not prospect_ids:
            return ()
        clauses = ["opportunities.prospect_id = ANY(CAST(:prospect_ids AS uuid[]))", "prospects.archived_at IS NULL"]
        parameters: dict[str, object] = {"prospect_ids": list(prospect_ids), "today": organization_today}
        if owner_membership_id is not None:
            clauses.append("opportunities.owner_membership_id = :owner_membership_id")
            parameters["owner_membership_id"] = owner_membership_id
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT opportunities.prospect_id, opportunities.currency_code,
                               COUNT(*) AS count,
                               COALESCE(SUM(opportunities.amount), 0) AS amount_total,
                               COALESCE(SUM(opportunities.amount * opportunities.probability / 100.0), 0)
                                   AS weighted_amount_total,
                               COUNT(*) FILTER (WHERE opportunities.stage_code IN ('discovery', 'qualification',
                                   'proposal', 'negotiation')) AS open_count,
                               COUNT(*) FILTER (WHERE opportunities.stage_code = 'won') AS won_count,
                               COUNT(*) FILTER (WHERE opportunities.stage_code = 'lost') AS lost_count,
                               COUNT(*) FILTER (WHERE opportunities.stage_code IN ('discovery', 'qualification',
                                   'proposal', 'negotiation') AND opportunities.expected_close_on < :today)
                                   AS overdue_open_count,
                               MIN(opportunities.expected_close_on) FILTER (WHERE opportunities.stage_code IN
                                   ('discovery', 'qualification', 'proposal', 'negotiation')) AS next_expected_close_on
                        FROM public.opportunities opportunities
                        JOIN public.prospects prospects ON prospects.id = opportunities.prospect_id
                        WHERE """
                        + " AND ".join(clauses)
                        + " GROUP BY opportunities.prospect_id, opportunities.currency_code"
                    ),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        grouped: dict[UUID, list[Mapping[str, object]]] = {}
        for row in rows:
            grouped.setdefault(cast(UUID, row["prospect_id"]), []).append(cast(Mapping[str, object], row))
        summaries: list[OpportunityProspectSummary] = []
        for prospect_id, entries in grouped.items():
            aggregates = tuple(
                OpportunityCurrencyAggregate(
                    currency_code=str(entry["currency_code"]).strip(),
                    count=int(cast(int, entry["count"])),
                    amount_total=cast(Decimal, entry["amount_total"]),
                    weighted_amount_total=cast(Decimal, entry["weighted_amount_total"]),
                    open_count=int(cast(int, entry["open_count"])),
                    won_count=int(cast(int, entry["won_count"])),
                    lost_count=int(cast(int, entry["lost_count"])),
                    overdue_open_count=int(cast(int, entry["overdue_open_count"])),
                )
                for entry in sorted(entries, key=lambda entry: str(entry["currency_code"]))
            )
            next_dates = [
                cast(date, entry["next_expected_close_on"]) for entry in entries if entry["next_expected_close_on"]
            ]
            summaries.append(
                OpportunityProspectSummary(
                    prospect_id=prospect_id,
                    open_count=sum(item.open_count for item in aggregates),
                    has_won_opportunity=any(item.won_count > 0 for item in aggregates),
                    next_expected_close_on=min(next_dates) if next_dates else None,
                    overdue_open_count=sum(item.overdue_open_count for item in aggregates),
                    aggregates_by_currency=aggregates,
                )
            )
        return tuple(sorted(summaries, key=lambda item: str(item.prospect_id)))


class SqlAlchemyOpportunityEventRepository(OpportunityEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: OpportunityEventView) -> OpportunityEventView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.opportunity_events (
                            id, organization_id, prospect_id, opportunity_id, actor_id, event_type,
                            from_stage, to_stage, from_version, resulting_version, changed_fields,
                            reason_code, reason_note, idempotency_key, command_fingerprint, occurred_at
                        ) VALUES (
                            :id, :organization_id, :prospect_id, :opportunity_id, :actor_id, :event_type,
                            :from_stage, :to_stage, :from_version, :resulting_version, CAST(:changed_fields AS jsonb),
                            :reason_code, :reason_note, :idempotency_key, :command_fingerprint, :occurred_at
                        ) RETURNING *
                        """
                    ),
                    {
                        "id": event.id,
                        "organization_id": event.organization_id,
                        "prospect_id": event.prospect_id,
                        "opportunity_id": event.opportunity_id,
                        "actor_id": event.actor_id,
                        "event_type": event.event_type.value,
                        "from_stage": event.from_stage.value if event.from_stage is not None else None,
                        "to_stage": event.to_stage.value if event.to_stage is not None else None,
                        "from_version": event.from_version,
                        "resulting_version": event.resulting_version,
                        "changed_fields": json.dumps(event.changed_fields),
                        "reason_code": event.reason_code,
                        "reason_note": event.reason_note,
                        "idempotency_key": event.idempotency_key,
                        "command_fingerprint": event.command_fingerprint,
                        "occurred_at": event.occurred_at,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _opportunity_event_from_row(cast(Mapping[str, object], row))

    async def get_by_idempotency_key(
        self, *, event_type: OpportunityEventType, idempotency_key: str
    ) -> OpportunityEventView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.opportunity_events
                        WHERE event_type = :event_type AND idempotency_key = :idempotency_key
                        """
                    ),
                    {"event_type": event_type.value, "idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _opportunity_event_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_for_opportunity(self, opportunity_id: UUID, *, limit: int) -> tuple[OpportunityEventView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.opportunity_events
                        WHERE opportunity_id = :opportunity_id
                        ORDER BY occurred_at DESC, id DESC LIMIT :limit
                        """
                    ),
                    {"opportunity_id": opportunity_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_opportunity_event_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[OpportunityEventView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.opportunity_events
                        WHERE prospect_id = :prospect_id
                        ORDER BY occurred_at DESC, id DESC LIMIT :limit
                        """
                    ),
                    {"prospect_id": prospect_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_opportunity_event_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def latest_open_stage(self, opportunity_id: UUID) -> OpportunityStageCode | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT to_stage FROM public.opportunity_events
                        WHERE opportunity_id = :opportunity_id
                          AND to_stage IN ('discovery', 'qualification', 'proposal', 'negotiation')
                        ORDER BY occurred_at DESC, id DESC LIMIT 1
                        """
                    ),
                    {"opportunity_id": opportunity_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return OpportunityStageCode(str(row["to_stage"])) if row is not None else None


def _opportunity_select(suffix: str) -> str:
    return (
        """
        SELECT opportunities.*,
               COALESCE(memberships.status = 'active', false) AS owner_membership_is_active
        FROM public.opportunities
        JOIN public.prospects ON prospects.id = opportunities.prospect_id
        LEFT JOIN public.memberships ON memberships.id = opportunities.owner_membership_id
        """
        + suffix
    )


def _opportunity_filters(
    *,
    prospect_id: UUID | None,
    owner_membership_id: UUID | None,
    stage_codes: tuple[OpportunityStageCode, ...],
    currency_code: str | None,
    search_text: str | None,
    expected_close_from: date | None,
    expected_close_to: date | None,
    overdue: bool | None,
    organization_today: date | None,
) -> tuple[list[str], dict[str, object]]:
    clauses = ["prospects.archived_at IS NULL"]
    parameters: dict[str, object] = {}
    if prospect_id is not None:
        clauses.append("opportunities.prospect_id = :prospect_id")
        parameters["prospect_id"] = prospect_id
    if owner_membership_id is not None:
        clauses.append("opportunities.owner_membership_id = :owner_membership_id")
        parameters["owner_membership_id"] = owner_membership_id
    if stage_codes:
        clauses.append("opportunities.stage_code = ANY(CAST(:stage_codes AS text[]))")
        parameters["stage_codes"] = [stage.value for stage in stage_codes]
    if currency_code is not None:
        clauses.append("opportunities.currency_code = :currency_code")
        parameters["currency_code"] = currency_code
    if search_text is not None:
        clauses.append("(opportunities.name ILIKE :search_text OR prospects.internal_alias ILIKE :search_text)")
        parameters["search_text"] = f"%{search_text}%"
    if expected_close_from is not None:
        clauses.append("opportunities.expected_close_on >= :expected_close_from")
        parameters["expected_close_from"] = expected_close_from
    if expected_close_to is not None:
        clauses.append("opportunities.expected_close_on <= :expected_close_to")
        parameters["expected_close_to"] = expected_close_to
    if overdue is not None:
        if organization_today is None:
            raise ValueError("Le jour de l’organisation est obligatoire pour filtrer les retards.")
        overdue_clause = (
            "opportunities.stage_code IN ('discovery', 'qualification', 'proposal', 'negotiation') "
            "AND opportunities.expected_close_on < :today"
        )
        clauses.append(f"({overdue_clause})" if overdue else f"NOT ({overdue_clause})")
        parameters["today"] = organization_today
    return clauses, parameters


def _opportunity_from_row(row: Mapping[str, object]) -> OpportunityView:
    loss_reason_code = cast(str | None, row["loss_reason_code"])
    return OpportunityView(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        prospect_id=cast(UUID, row["prospect_id"]),
        owner_membership_id=cast(UUID, row["owner_membership_id"]),
        name=str(row["name"]),
        amount=cast(Decimal, row["amount"]),
        currency_code=str(row["currency_code"]).strip(),
        probability=int(cast(int, row["probability"])),
        stage_code=OpportunityStageCode(str(row["stage_code"])),
        expected_close_on=cast(date, row["expected_close_on"]),
        loss_reason_code=OpportunityLossReasonCode(loss_reason_code) if loss_reason_code is not None else None,
        loss_reason_note=cast(str | None, row["loss_reason_note"]),
        closed_at=cast(datetime | None, row["closed_at"]),
        created_by=cast(UUID, row["created_by"]),
        version=int(cast(int, row["version"])),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
        owner_membership_is_active=bool(row.get("owner_membership_is_active", True)),
    )


def _opportunity_event_from_row(row: Mapping[str, object]) -> OpportunityEventView:
    return OpportunityEventView(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        prospect_id=cast(UUID, row["prospect_id"]),
        opportunity_id=cast(UUID, row["opportunity_id"]),
        actor_id=cast(UUID, row["actor_id"]),
        event_type=OpportunityEventType(str(row["event_type"])),
        from_stage=OpportunityStageCode(str(row["from_stage"])) if row["from_stage"] is not None else None,
        to_stage=OpportunityStageCode(str(row["to_stage"])) if row["to_stage"] is not None else None,
        from_version=int(cast(int, row["from_version"])),
        resulting_version=int(cast(int, row["resulting_version"])),
        changed_fields=dict(cast(Mapping[str, str], row["changed_fields"])),
        reason_code=cast(str | None, row["reason_code"]),
        reason_note=cast(str | None, row["reason_note"]),
        idempotency_key=str(row["idempotency_key"]),
        command_fingerprint=str(row["command_fingerprint"]),
        occurred_at=cast(datetime, row["occurred_at"]),
    )
