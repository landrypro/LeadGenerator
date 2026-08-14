from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

from ..domain.audit import (
    AuditAction,
    AuditActorKind,
    AuditEventDraft,
    AuditScope,
    AuditSource,
)
from .tenancy import ActorContext, TenantContext


def tenant_audit_event(
    context: TenantContext,
    action: AuditAction,
    entity_id: UUID,
    metadata: Mapping[str, object] | None = None,
) -> AuditEventDraft:
    return _event(
        scope=AuditScope.TENANT,
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        action=action,
        entity_id=entity_id,
        metadata=metadata,
    )


def platform_audit_event(
    context: ActorContext,
    action: AuditAction,
    entity_id: UUID,
    metadata: Mapping[str, object] | None = None,
    *,
    organization_id: UUID | None = None,
) -> AuditEventDraft:
    return _event(
        scope=AuditScope.PLATFORM,
        organization_id=organization_id,
        actor_id=context.actor_id,
        request_id=context.request_id,
        action=action,
        entity_id=entity_id,
        metadata=metadata,
    )


def _event(
    *,
    scope: AuditScope,
    organization_id: UUID | None,
    actor_id: UUID,
    request_id: str,
    action: AuditAction,
    entity_id: UUID,
    metadata: Mapping[str, object] | None,
) -> AuditEventDraft:
    return AuditEventDraft(
        id=uuid4(),
        scope=scope,
        action=action,
        entity_type=_entity_type(action),
        entity_id=entity_id,
        actor_kind=AuditActorKind.USER,
        actor_id=actor_id,
        organization_id=organization_id,
        request_id=request_id,
        correlation_id=request_id,
        source=AuditSource.API,
        metadata=metadata or {},
    )


def _entity_type(action: AuditAction) -> str:
    if action in {
        AuditAction.ORGANIZATION_UPDATED,
        AuditAction.ORGANIZATION_ACTIVATED,
        AuditAction.ORGANIZATION_PROVISIONED,
        AuditAction.ORGANIZATION_SUSPENDED,
        AuditAction.ORGANIZATION_REACTIVATED,
    }:
        return "organization"
    if action in {AuditAction.MEMBERSHIP_ROLE_CHANGED, AuditAction.MEMBERSHIP_STATUS_CHANGED}:
        return "membership"
    if action is AuditAction.ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED:
        return "user"
    return "invitation"
