"""Cas d’usage internes de P52-03 : catalogue et contrats."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from ...domain.audit import AuditAction
from ...domain.catalog import (
    CatalogValidationError,
    ContractState,
    CurrencyCode,
    EntitlementValue,
    PlanCode,
)
from ..audit_events import platform_audit_event
from ..errors import (
    CatalogApprovalRequired,
    CatalogConcurrentUpdate,
    CatalogInvalidContract,
    CatalogInvalidTransition,
    CatalogResourceConflict,
    CatalogResourceNotFound,
    CatalogSafetyCeilingExceeded,
    CatalogServiceUnavailable,
    InsufficientCapability,
)
from ..ports.catalog import (
    CatalogAuditedUnitOfWorkFactory,
    CatalogMutationResultCode,
    CatalogPlanVersionView,
    CatalogPlanView,
    OrganizationCatalogReader,
    OrganizationCatalogView,
    OrganizationPlanContractView,
    PlanContractOverrideView,
)
from ..ports.clock import Clock
from ..tenancy import ActorContext, TenantContext


@dataclass(frozen=True, slots=True)
class CreateCatalogPlanCommand:
    code: PlanCode
    display_order: int
    operation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.display_order < 0:
            raise CatalogValidationError("L’ordre d’affichage doit être positif ou nul.")


@dataclass(frozen=True, slots=True)
class CreateCatalogPlanVersionCommand:
    plan_id: UUID
    version_number: int
    currency: CurrencyCode
    billing_cycle: str
    amount_excluding_tax_minor: int
    effective_from: datetime
    effective_until: datetime | None
    entitlements: tuple[EntitlementValue, ...]
    operation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.version_number < 1:
            raise CatalogValidationError("Le numéro de version doit être supérieur à zéro.")
        if self.billing_cycle not in {"monthly", "annual", "custom_contract"}:
            raise CatalogValidationError("Le cycle de facturation est inconnu.")
        if self.amount_excluding_tax_minor < 0:
            raise CatalogValidationError("Le montant hors taxes ne peut pas être négatif.")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise CatalogValidationError("La fin de validité doit être postérieure au début.")
        keys = {item.key for item in self.entitlements}
        if len(self.entitlements) != 8 or len(keys) != 8:
            raise CatalogValidationError("Une version de plan doit définir exactement les huit droits du registre.")


@dataclass(frozen=True, slots=True)
class AttachOrganizationPlanContractCommand:
    organization_id: UUID
    plan_version_id: UUID
    state: ContractState
    effective_from: datetime
    effective_until: datetime | None
    operation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.state not in {ContractState.PENDING, ContractState.ACTIVE}:
            raise CatalogValidationError("Un contrat initial doit être en attente ou actif.")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise CatalogValidationError("La fin du contrat doit être postérieure au début.")


@dataclass(frozen=True, slots=True)
class ProposePlanContractOverrideCommand:
    contract_id: UUID
    value: EntitlementValue
    justification: str
    starts_at: datetime
    ends_at: datetime
    operation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not 1 <= len(self.justification.strip()) <= 512:
            raise CatalogValidationError("La justification doit contenir entre 1 et 512 caractères.")
        if self.ends_at <= self.starts_at:
            raise CatalogValidationError("La fin d’une dérogation doit être postérieure à son début.")


def _require_platform(has_platform_capability: bool) -> None:
    if not has_platform_capability:
        raise InsufficientCapability


def _raise_for_result(code: CatalogMutationResultCode, current_version: int | None = None) -> None:
    if code is CatalogMutationResultCode.NOT_FOUND:
        raise CatalogResourceNotFound
    if code is CatalogMutationResultCode.CONFLICT:
        raise CatalogResourceConflict
    if code is CatalogMutationResultCode.VERSION_CONFLICT:
        raise CatalogConcurrentUpdate(current_version)
    if code is CatalogMutationResultCode.INVALID_TRANSITION:
        raise CatalogInvalidTransition
    if code is CatalogMutationResultCode.APPROVAL_REQUIRED:
        raise CatalogApprovalRequired
    if code is CatalogMutationResultCode.INVALID_CONTRACT:
        raise CatalogInvalidContract
    if code is CatalogMutationResultCode.SAFETY_CEILING_EXCEEDED:
        raise CatalogSafetyCeilingExceeded


class GetOrganizationCatalogUseCase:
    """Vue tenant minimale : contrat courant et décisions de droits, sans prix ni données d'approbation."""

    def __init__(self, reader: OrganizationCatalogReader, clock: Clock) -> None:
        self._reader = reader
        self._clock = clock

    async def execute(self, *, context: TenantContext, has_capability: bool) -> OrganizationCatalogView:
        if not has_capability:
            raise InsufficientCapability
        return await self._reader.get_current(context=context, now=self._clock.now())


class CatalogAdministrationUseCases:
    """Mutations plateforme du catalogue et des contrats, exposées par l'API interne P52-07."""

    def __init__(self, factory: CatalogAuditedUnitOfWorkFactory, clock: Clock) -> None:
        self._factory = factory
        self._clock = clock

    async def create_plan(
        self, *, context: ActorContext, command: CreateCatalogPlanCommand, has_platform_capability: bool
    ) -> CatalogPlanView:
        _require_platform(has_platform_capability)
        plan_id = uuid5(NAMESPACE_URL, f"catalog-plan:{command.operation_id}")
        async with self._factory(context) as unit:
            result = await unit.mutations.create_plan(
                plan_id=plan_id,
                operation_id=command.operation_id,
                code=command.code,
                display_order=command.display_order,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.plan is None:
                raise CatalogServiceUnavailable("La création du plan n’a retourné aucune ressource.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.plan
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_PLAN_CREATED,
                    result.plan.id,
                    {"plan_code": result.plan.code.value, "display_order": result.plan.display_order},
                )
            )
            await unit.commit()
            return result.plan

    async def create_plan_version(
        self, *, context: ActorContext, command: CreateCatalogPlanVersionCommand, has_platform_capability: bool
    ) -> CatalogPlanVersionView:
        _require_platform(has_platform_capability)
        version_id = uuid5(NAMESPACE_URL, f"catalog-version:{command.operation_id}")
        async with self._factory(context) as unit:
            result = await unit.mutations.create_plan_version(
                version_id=version_id,
                operation_id=command.operation_id,
                plan_id=command.plan_id,
                version_number=command.version_number,
                currency=command.currency,
                billing_cycle=command.billing_cycle,
                amount_excluding_tax_minor=command.amount_excluding_tax_minor,
                effective_from=command.effective_from,
                effective_until=command.effective_until,
                entitlements=command.entitlements,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.plan_version is None:
                raise CatalogServiceUnavailable("La création de la version n’a retourné aucune ressource.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.plan_version
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_PLAN_VERSION_CREATED,
                    result.plan_version.id,
                    {"plan_id": result.plan_version.plan_id, "version_number": result.plan_version.version_number},
                )
            )
            await unit.commit()
            return result.plan_version

    async def publish_plan_version(
        self,
        *,
        context: ActorContext,
        version_id: UUID,
        expected_version: int,
        has_platform_capability: bool,
        operation_id: UUID | None = None,
    ) -> CatalogPlanVersionView:
        _require_platform(has_platform_capability)
        if expected_version < 1:
            raise CatalogValidationError("La version attendue doit être positive.")
        operation_id = operation_id or uuid4()
        async with self._factory(context) as unit:
            result = await unit.mutations.publish_plan_version(
                version_id=version_id,
                operation_id=operation_id,
                expected_version=expected_version,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.plan_version is None:
                raise CatalogServiceUnavailable("La publication n’a retourné aucune version.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.plan_version
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_PLAN_VERSION_PUBLISHED,
                    result.plan_version.id,
                    {"plan_id": result.plan_version.plan_id, "version_number": result.plan_version.version_number},
                )
            )
            await unit.commit()
            return result.plan_version

    async def attach_organization_contract(
        self, *, context: ActorContext, command: AttachOrganizationPlanContractCommand, has_platform_capability: bool
    ) -> OrganizationPlanContractView:
        _require_platform(has_platform_capability)
        contract_id = uuid5(NAMESPACE_URL, f"catalog-contract:{command.operation_id}")
        async with self._factory(context) as unit:
            result = await unit.mutations.attach_organization_contract(
                contract_id=contract_id,
                operation_id=command.operation_id,
                organization_id=command.organization_id,
                plan_version_id=command.plan_version_id,
                state=command.state,
                effective_from=command.effective_from,
                effective_until=command.effective_until,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.contract is None:
                raise CatalogServiceUnavailable("Le rattachement du contrat n’a retourné aucune ressource.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.contract
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_CONTRACT_ATTACHED,
                    result.contract.id,
                    {
                        "organization_id": result.contract.organization_id,
                        "plan_version_id": result.contract.plan_version_id,
                        "state": result.contract.state.value,
                    },
                    organization_id=result.contract.organization_id,
                )
            )
            await unit.commit()
            return result.contract

    async def change_contract_state(
        self,
        *,
        context: ActorContext,
        contract_id: UUID,
        expected_version: int,
        state: ContractState,
        has_platform_capability: bool,
        operation_id: UUID | None = None,
    ) -> OrganizationPlanContractView:
        _require_platform(has_platform_capability)
        if expected_version < 1:
            raise CatalogValidationError("La version attendue doit être positive.")
        operation_id = operation_id or uuid4()
        async with self._factory(context) as unit:
            result = await unit.mutations.change_contract_state(
                contract_id=contract_id,
                operation_id=operation_id,
                expected_version=expected_version,
                state=state,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.contract is None:
                raise CatalogServiceUnavailable("Le contrat mis à jour n’a retourné aucune ressource.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.contract
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_CONTRACT_STATE_CHANGED,
                    result.contract.id,
                    {
                        "organization_id": result.contract.organization_id,
                        "new_state": result.contract.state.value,
                        "version": result.contract.version,
                    },
                    organization_id=result.contract.organization_id,
                )
            )
            await unit.commit()
            return result.contract

    async def propose_contract_override(
        self,
        *,
        context: ActorContext,
        command: ProposePlanContractOverrideCommand,
        has_platform_capability: bool,
    ) -> PlanContractOverrideView:
        _require_platform(has_platform_capability)
        override_id = uuid5(NAMESPACE_URL, f"catalog-contract-override:{command.operation_id}")
        async with self._factory(context) as unit:
            result = await unit.mutations.propose_contract_override(
                override_id=override_id,
                operation_id=command.operation_id,
                contract_id=command.contract_id,
                value=command.value,
                justification=command.justification.strip(),
                starts_at=command.starts_at,
                ends_at=command.ends_at,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.contract_override is None:
                raise CatalogServiceUnavailable("La proposition de dérogation n’a retourné aucune ressource.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.contract_override
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_CONTRACT_OVERRIDE_PROPOSED,
                    result.contract_override.id,
                    {
                        "organization_id": result.contract_override.organization_id,
                        "contract_id": result.contract_override.contract_id,
                        "entitlement_key": result.contract_override.entitlement_key.value,
                    },
                    organization_id=result.contract_override.organization_id,
                )
            )
            await unit.commit()
            return result.contract_override

    async def approve_contract_override(
        self,
        *,
        context: ActorContext,
        override_id: UUID,
        expected_version: int,
        has_platform_capability: bool,
        operation_id: UUID | None = None,
    ) -> PlanContractOverrideView:
        _require_platform(has_platform_capability)
        if expected_version < 1:
            raise CatalogValidationError("La version attendue doit être positive.")
        operation_id = operation_id or uuid4()
        async with self._factory(context) as unit:
            result = await unit.mutations.approve_contract_override(
                override_id=override_id,
                operation_id=operation_id,
                expected_version=expected_version,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.contract_override is None:
                raise CatalogServiceUnavailable("L’approbation de dérogation n’a retourné aucune ressource.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.contract_override
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_CONTRACT_OVERRIDE_APPROVED,
                    result.contract_override.id,
                    {
                        "organization_id": result.contract_override.organization_id,
                        "contract_id": result.contract_override.contract_id,
                        "entitlement_key": result.contract_override.entitlement_key.value,
                        "version": result.contract_override.version,
                    },
                    organization_id=result.contract_override.organization_id,
                )
            )
            await unit.commit()
            return result.contract_override

    async def revoke_contract_override(
        self,
        *,
        context: ActorContext,
        override_id: UUID,
        expected_version: int,
        has_platform_capability: bool,
        operation_id: UUID | None = None,
    ) -> PlanContractOverrideView:
        _require_platform(has_platform_capability)
        if expected_version < 1:
            raise CatalogValidationError("La version attendue doit être positive.")
        operation_id = operation_id or uuid4()
        async with self._factory(context) as unit:
            result = await unit.mutations.revoke_contract_override(
                override_id=override_id,
                operation_id=operation_id,
                expected_version=expected_version,
                now=self._clock.now(),
            )
            _raise_for_result(result.code, result.current_version)
            if result.contract_override is None:
                raise CatalogServiceUnavailable("La révocation de dérogation n’a retourné aucune ressource.")
            if result.code is CatalogMutationResultCode.REPLAYED:
                return result.contract_override
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.CATALOG_CONTRACT_OVERRIDE_REVOKED,
                    result.contract_override.id,
                    {
                        "organization_id": result.contract_override.organization_id,
                        "contract_id": result.contract_override.contract_id,
                        "entitlement_key": result.contract_override.entitlement_key.value,
                        "version": result.contract_override.version,
                    },
                    organization_id=result.contract_override.organization_id,
                )
            )
            await unit.commit()
            return result.contract_override
