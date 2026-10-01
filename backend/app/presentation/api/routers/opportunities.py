from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    IdempotencyKeyReused,
    InsufficientCapability,
    OpportunityCursorInvalid,
    OpportunityOwnerInactive,
    OpportunityParentArchived,
    OpportunityResourceNotFound,
    OpportunityTransitionInvalid,
    OpportunityVersionConflict,
    ProspectResourceNotFound,
    ProspectServiceUnavailable,
)
from ....application.tenancy import TenantContext
from ....domain.identity import capabilities_for
from ....domain.opportunity import OpportunityDraft, OpportunityStageCode, OpportunityValidationError, OpportunityView
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    OpportunityCreateRequest,
    OpportunityReopenRequest,
    OpportunityTransitionRequest,
    OpportunityUpdateRequest,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api", tags=["opportunities"])


@router.get("/prospects/opportunity-summaries")
async def list_opportunity_summaries(
    request: Request,
    container: ContainerDependency,
    prospect_id: tuple[UUID, ...] = Query(default=()),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_opportunity_summaries is None:
            raise ProspectServiceUnavailable
        summaries = await container.list_opportunity_summaries.execute(
            context=_tenant_context(request, authentication),
            prospect_ids=prospect_id,
            can_read=_has_capability(authentication, "opportunities:read"),
            can_manage=_can_manage(authentication),
            current_membership_id=_membership_id(authentication),
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse({"items": [_summary_payload(item) for item in summaries]}, headers=NO_STORE_HEADERS)


@router.post("/prospects/{prospect_id}/opportunities", status_code=201)
async def create_opportunity(
    prospect_id: UUID, payload: OpportunityCreateRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_opportunity is None:
            raise ProspectServiceUnavailable
        membership_id = _membership_id(authentication)
        opportunity = await container.create_opportunity.execute(
            context=_tenant_context(request, authentication),
            draft=OpportunityDraft(
                prospect_id=prospect_id,
                owner_membership_id=payload.owner_membership_id or _required_membership(authentication),
                name=payload.name,
                amount=_amount(payload.amount),
                currency_code=payload.currency_code,
                probability=payload.probability,
                expected_close_on=payload.expected_close_on,
                idempotency_key=payload.idempotency_key,
            ),
            can_create=_has_capability(authentication, "opportunities:create"),
            can_manage=_can_manage(authentication),
            current_membership_id=membership_id,
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_opportunity_payload(opportunity), status_code=201, headers=NO_STORE_HEADERS)


@router.get("/prospects/{prospect_id}/opportunities")
async def list_prospect_opportunities(
    prospect_id: UUID,
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = None,
) -> Response:
    return await _list_opportunities(
        request=request,
        container=container,
        limit=limit,
        cursor=cursor,
        prospect_id=prospect_id,
    )


@router.get("/opportunities")
async def list_opportunities(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = None,
    q: str | None = Query(default=None, min_length=1, max_length=160),
    stage: tuple[str, ...] = Query(default=()),
    owner_membership_id: UUID | None = None,
    currency_code: str | None = Query(default=None, min_length=3, max_length=3),
    expected_close_from: str | None = None,
    expected_close_to: str | None = None,
    overdue: bool | None = None,
    prospect_id: UUID | None = None,
) -> Response:
    try:
        stages = tuple(OpportunityStageCode(value) for value in stage)
        close_from = date.fromisoformat(expected_close_from) if expected_close_from else None
        close_to = date.fromisoformat(expected_close_to) if expected_close_to else None
    except ValueError:
        return api_error(request, 422, "opportunity_command_invalid", "Les filtres d’opportunité sont invalides.")
    return await _list_opportunities(
        request=request,
        container=container,
        limit=limit,
        cursor=cursor,
        prospect_id=prospect_id,
        owner_membership_id=owner_membership_id,
        stage_codes=stages,
        currency_code=currency_code,
        search_text=q,
        expected_close_from=close_from,
        expected_close_to=close_to,
        overdue=overdue,
    )


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(opportunity_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_opportunity is None:
            raise ProspectServiceUnavailable
        opportunity = await container.get_opportunity.execute(
            context=_tenant_context(request, authentication),
            opportunity_id=opportunity_id,
            can_read=_has_capability(authentication, "opportunities:read"),
            can_manage=_can_manage(authentication),
            current_membership_id=_membership_id(authentication),
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_opportunity_payload(opportunity), headers=NO_STORE_HEADERS)


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity(
    opportunity_id: UUID, payload: OpportunityUpdateRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_opportunity is None:
            raise ProspectServiceUnavailable
        changes: dict[str, object] = {
            key: value
            for key, value in payload.model_dump(exclude={"version", "idempotency_key"}, exclude_none=True).items()
        }
        if "amount" in changes:
            changes["amount"] = _amount(str(changes["amount"]))
        opportunity = await container.update_opportunity.execute(
            context=_tenant_context(request, authentication),
            opportunity_id=opportunity_id,
            expected_version=payload.version,
            changes=changes,
            idempotency_key=payload.idempotency_key,
            can_update=_has_capability(authentication, "opportunities:update"),
            can_manage=_can_manage(authentication),
            current_membership_id=_membership_id(authentication),
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_opportunity_payload(opportunity), headers=NO_STORE_HEADERS)


@router.post("/opportunities/{opportunity_id}/stage-transitions")
async def transition_opportunity(
    opportunity_id: UUID, payload: OpportunityTransitionRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.transition_opportunity is None:
            raise ProspectServiceUnavailable
        opportunity = await container.transition_opportunity.execute(
            context=_tenant_context(request, authentication),
            opportunity_id=opportunity_id,
            expected_version=payload.version,
            to_stage=OpportunityStageCode(payload.to_stage),
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            idempotency_key=payload.idempotency_key,
            can_close=_has_capability(authentication, "opportunities:close"),
            can_manage=_can_manage(authentication),
            current_membership_id=_membership_id(authentication),
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_opportunity_payload(opportunity), headers=NO_STORE_HEADERS)


@router.post("/opportunities/{opportunity_id}/reopen")
async def reopen_opportunity(
    opportunity_id: UUID, payload: OpportunityReopenRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.reopen_opportunity is None:
            raise ProspectServiceUnavailable
        opportunity = await container.reopen_opportunity.execute(
            context=_tenant_context(request, authentication),
            opportunity_id=opportunity_id,
            expected_version=payload.version,
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            probability=payload.probability,
            idempotency_key=payload.idempotency_key,
            can_reopen=_has_capability(authentication, "opportunities:reopen"),
            can_manage=_can_manage(authentication),
            current_membership_id=_membership_id(authentication),
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_opportunity_payload(opportunity), headers=NO_STORE_HEADERS)


@router.get("/opportunities/{opportunity_id}/events")
async def list_opportunity_events(
    opportunity_id: UUID,
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_opportunity_events is None:
            raise ProspectServiceUnavailable
        events = await container.list_opportunity_events.execute(
            context=_tenant_context(request, authentication),
            opportunity_id=opportunity_id,
            limit=limit,
            can_read=_has_capability(authentication, "opportunities:read"),
            can_manage=_can_manage(authentication),
            current_membership_id=_membership_id(authentication),
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse({"items": [_event_payload(event) for event in events]}, headers=NO_STORE_HEADERS)


async def _list_opportunities(
    *,
    request: Request,
    container: ContainerDependency,
    limit: int,
    cursor: str | None,
    prospect_id: UUID | None,
    owner_membership_id: UUID | None = None,
    stage_codes: tuple[OpportunityStageCode, ...] = (),
    currency_code: str | None = None,
    search_text: str | None = None,
    expected_close_from: date | None = None,
    expected_close_to: date | None = None,
    overdue: bool | None = None,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_opportunities is None:
            raise ProspectServiceUnavailable
        page = await container.list_opportunities.execute(
            context=_tenant_context(request, authentication),
            can_read=_has_capability(authentication, "opportunities:read"),
            can_manage=_can_manage(authentication),
            current_membership_id=_membership_id(authentication),
            limit=limit,
            cursor=cursor,
            prospect_id=prospect_id,
            owner_membership_id=owner_membership_id,
            stage_codes=stage_codes,
            currency_code=currency_code,
            search_text=search_text,
            expected_close_from=expected_close_from,
            expected_close_to=expected_close_to,
            overdue=overdue,
        )
    except Exception as error:
        response = _opportunity_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        {
            "items": [_opportunity_payload(item) for item in page.items],
            "next_cursor": page.next_cursor,
            "has_more": page.has_more,
            "aggregates_by_currency": [_aggregate_payload(item) for item in page.aggregates_by_currency],
        },
        headers=NO_STORE_HEADERS,
    )


async def _authenticated_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _tenant_context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None or not membership.is_active:
        raise InsufficientCapability
    return TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _membership_id(authentication: RequestAuthentication) -> UUID | None:
    membership = authentication.identity.active_membership
    return membership.id if membership is not None and membership.is_active else None


def _required_membership(authentication: RequestAuthentication) -> UUID:
    membership_id = _membership_id(authentication)
    if membership_id is None:
        raise InsufficientCapability
    return membership_id


def _has_capability(authentication: RequestAuthentication, capability: str) -> bool:
    return capability in capabilities_for(authentication.identity.user, authentication.identity.active_membership)


def _can_manage(authentication: RequestAuthentication) -> bool:
    membership = authentication.identity.active_membership
    return membership is not None and membership.role.value in {"admin", "manager"}


def _amount(value: str) -> Decimal:
    if "e" in value.lower():
        raise OpportunityValidationError("Le montant doit être écrit sans notation exponentielle.", field="amount")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise OpportunityValidationError("Le montant est invalide.", field="amount") from error
    return result


def _opportunity_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 400, "csrf_failed", "La protection de la session a refusé la requête.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "opportunity_action_forbidden", "Action opportunité non autorisée.")
    if isinstance(error, ProspectResourceNotFound):
        return api_error(request, 404, "prospect_not_found", "Prospect introuvable.")
    if isinstance(error, OpportunityResourceNotFound):
        return api_error(request, 404, "opportunity_not_found", "Opportunité introuvable.")
    if isinstance(error, OpportunityVersionConflict):
        fields = {"current_version": str(error.current_version)} if error.current_version is not None else {}
        return api_error(
            request,
            409,
            "opportunity_version_conflict",
            "L’opportunité a changé depuis sa lecture.",
            fields=fields,
        )
    if isinstance(error, IdempotencyKeyReused):
        return api_error(request, 409, "opportunity_idempotency_conflict", "La clé de requête a déjà été utilisée.")
    if isinstance(error, OpportunityOwnerInactive):
        return api_error(request, 409, "opportunity_owner_inactive", "Le responsable doit être réaffecté.")
    if isinstance(error, OpportunityParentArchived):
        return api_error(request, 409, "opportunity_parent_archived", "Le prospect parent est archivé.")
    if isinstance(error, OpportunityCursorInvalid):
        return api_error(request, 422, "opportunity_cursor_invalid", "Le curseur est invalide.")
    if isinstance(error, OpportunityTransitionInvalid):
        return api_error(request, 422, "opportunity_transition_invalid", str(error))
    if isinstance(error, OpportunityValidationError):
        return api_error(
            request,
            422,
            "opportunity_command_invalid",
            "La commande opportunité est invalide.",
            fields={error.field: str(error)} if error.field else {},
        )
    if isinstance(error, (AuthenticationServiceUnavailable, ProspectServiceUnavailable)):
        return api_error(request, 503, "opportunity_service_unavailable", "Le module opportunités est indisponible.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "opportunity_command_invalid", "La commande opportunité est invalide.")
    return None


def _opportunity_payload(item: OpportunityView) -> dict[str, object]:
    today = datetime.now(UTC).date()
    return {
        "id": str(item.id),
        "prospect_id": str(item.prospect_id),
        "owner_membership_id": str(item.owner_membership_id),
        "owner_membership_is_active": item.owner_membership_is_active,
        "name": item.name,
        "amount": f"{item.amount:.4f}",
        "currency_code": item.currency_code,
        "probability": item.probability,
        "weighted_amount": f"{item.weighted_amount:.4f}",
        "stage_code": item.stage_code.value,
        "expected_close_on": item.expected_close_on.isoformat(),
        "overdue": item.stage_code
        in {
            OpportunityStageCode.DISCOVERY,
            OpportunityStageCode.QUALIFICATION,
            OpportunityStageCode.PROPOSAL,
            OpportunityStageCode.NEGOTIATION,
        }
        and item.expected_close_on < today,
        "loss_reason_code": item.loss_reason_code.value if item.loss_reason_code else None,
        "loss_reason_note": item.loss_reason_note,
        "closed_at": item.closed_at.isoformat() if item.closed_at else None,
        "version": item.version,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _event_payload(event: object) -> dict[str, object]:
    from ....domain.opportunity import OpportunityEventView

    item = event if isinstance(event, OpportunityEventView) else None
    assert item is not None
    return {
        "id": str(item.id),
        "opportunity_id": str(item.opportunity_id),
        "actor_id": str(item.actor_id),
        "event_type": item.event_type.value,
        "from_stage": item.from_stage.value if item.from_stage else None,
        "to_stage": item.to_stage.value if item.to_stage else None,
        "from_version": item.from_version,
        "resulting_version": item.resulting_version,
        "changed_fields": item.changed_fields,
        "reason_code": item.reason_code,
        "reason_note": item.reason_note,
        "occurred_at": item.occurred_at.isoformat(),
    }


def _aggregate_payload(item: object) -> dict[str, object]:
    from ....domain.opportunity import OpportunityCurrencyAggregate

    aggregate = item if isinstance(item, OpportunityCurrencyAggregate) else None
    assert aggregate is not None
    return {
        "currency_code": aggregate.currency_code,
        "count": aggregate.count,
        "amount_total": f"{aggregate.amount_total:.4f}",
        "weighted_amount_total": f"{aggregate.weighted_amount_total:.4f}",
        "open_count": aggregate.open_count,
        "won_count": aggregate.won_count,
        "lost_count": aggregate.lost_count,
        "overdue_open_count": aggregate.overdue_open_count,
    }


def _summary_payload(item: object) -> dict[str, object]:
    from ....domain.opportunity import OpportunityProspectSummary

    summary = item if isinstance(item, OpportunityProspectSummary) else None
    assert summary is not None
    return {
        "prospect_id": str(summary.prospect_id),
        "open_count": summary.open_count,
        "has_won_opportunity": summary.has_won_opportunity,
        "next_expected_close_on": (
            summary.next_expected_close_on.isoformat() if summary.next_expected_close_on else None
        ),
        "overdue_open_count": summary.overdue_open_count,
        "aggregates_by_currency": [_aggregate_payload(aggregate) for aggregate in summary.aggregates_by_currency],
    }
