"""Règles déterministes du catalogue et des droits commerciaux P5.2.

Ce module est sans dépendance de base de données ou de fournisseur.  Il ne
déclenche ni paiement, ni facture, ni appel externe : il transforme seulement
des sources déjà validées en une décision explicable et fermée par défaut.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


class CatalogValidationError(ValueError):
    """Une valeur de catalogue ne respecte pas le registre fermé."""


class PlanCode(StrEnum):
    FREEMIUM = "freemium"
    STARTER = "starter"
    BUSINESS = "business"
    CUSTOM = "custom"


class CurrencyCode(StrEnum):
    CAD = "CAD"
    USD = "USD"
    EUR = "EUR"
    XAF = "XAF"


class PlanState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class PlanVersionState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ContractState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


class OverrideState(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class EntitlementKey(StrEnum):
    ACTIVE_MEMBERS_MAX = "seats.active_members.max"
    PENDING_INVITATIONS_MAX = "seats.pending_invitations.max"
    ACTIVE_PROSPECTS_MAX = "prospects.active.max"
    MONTHLY_EXPORTS_MAX = "exports.monthly.max"
    IMPORT_ROWS_PER_RUN_MAX = "imports.rows_per_run.max"
    GOOGLE_PAID_CALLS_ENABLED = "google.paid_calls.enabled"
    AUTOMATION_PREPARE_ENABLED = "automation.prepare.enabled"
    AUTOMATION_EXECUTE_ENABLED = "automation.execute.enabled"


class EntitlementKind(StrEnum):
    LIMIT = "limit"
    SWITCH = "switch"


class EntitlementDecisionCode(StrEnum):
    ALLOWED = "allowed"
    ENTITLEMENT_DISABLED = "entitlement_disabled"
    DENY_UNKNOWN_CONTRACT = "deny_unknown_contract"
    ENTITLEMENT_UNKNOWN = "entitlement_unknown"
    SAFETY_CEILING_EXCEEDED = "safety_ceiling_exceeded"


class EntitlementDecisionReason(StrEnum):
    """Mot stable, sans donnée commerciale, qui explique une décision fermée."""

    CONTRACT_NOT_ACTIVE = "contract_not_active"
    AMBIGUOUS_ACTIVE_CONTRACT = "ambiguous_active_contract"
    CATALOG_VERSION_NOT_PUBLISHED = "catalog_version_not_published"
    CATALOG_VERSION_NOT_EFFECTIVE = "catalog_version_not_effective"
    CONTRACT_CURRENCY_MISMATCH = "contract_currency_mismatch"
    PLAN_ENTITLEMENT_MISSING = "plan_entitlement_missing"
    OVERRIDE_EXPIRED = "override_expired"
    OVERRIDE_NOT_APPROVED = "override_not_approved"
    OVERRIDE_KIND_MISMATCH = "override_kind_mismatch"
    SAFETY_CEILING_EXCEEDED = "safety_ceiling_exceeded"


class EntitlementProvenanceSource(StrEnum):
    CONTRACT = "contract"
    PLAN_VERSION = "plan_version"
    OVERRIDE = "override"
    SAFETY_CEILING = "safety_ceiling"


@dataclass(frozen=True, slots=True)
class EntitlementProvenance:
    """Une source examinée par le calcul, dans son ordre de priorité."""

    source: EntitlementProvenanceSource
    applied: bool
    reason: EntitlementDecisionReason | None = None


@dataclass(frozen=True, slots=True)
class EntitlementDefinition:
    key: EntitlementKey
    kind: EntitlementKind
    unit: str
    scope: str


ENTITLEMENT_REGISTRY: Final[dict[EntitlementKey, EntitlementDefinition]] = {
    EntitlementKey.ACTIVE_MEMBERS_MAX: EntitlementDefinition(
        EntitlementKey.ACTIVE_MEMBERS_MAX, EntitlementKind.LIMIT, "seat", "organization"
    ),
    EntitlementKey.PENDING_INVITATIONS_MAX: EntitlementDefinition(
        EntitlementKey.PENDING_INVITATIONS_MAX, EntitlementKind.LIMIT, "reserved_seat", "organization"
    ),
    EntitlementKey.ACTIVE_PROSPECTS_MAX: EntitlementDefinition(
        EntitlementKey.ACTIVE_PROSPECTS_MAX, EntitlementKind.LIMIT, "prospect", "organization"
    ),
    EntitlementKey.MONTHLY_EXPORTS_MAX: EntitlementDefinition(
        EntitlementKey.MONTHLY_EXPORTS_MAX, EntitlementKind.LIMIT, "export", "period"
    ),
    EntitlementKey.IMPORT_ROWS_PER_RUN_MAX: EntitlementDefinition(
        EntitlementKey.IMPORT_ROWS_PER_RUN_MAX, EntitlementKind.LIMIT, "row", "run"
    ),
    EntitlementKey.GOOGLE_PAID_CALLS_ENABLED: EntitlementDefinition(
        EntitlementKey.GOOGLE_PAID_CALLS_ENABLED, EntitlementKind.SWITCH, "boolean", "organization"
    ),
    EntitlementKey.AUTOMATION_PREPARE_ENABLED: EntitlementDefinition(
        EntitlementKey.AUTOMATION_PREPARE_ENABLED, EntitlementKind.SWITCH, "boolean", "organization"
    ),
    EntitlementKey.AUTOMATION_EXECUTE_ENABLED: EntitlementDefinition(
        EntitlementKey.AUTOMATION_EXECUTE_ENABLED, EntitlementKind.SWITCH, "boolean", "organization"
    ),
}


@dataclass(frozen=True, slots=True)
class EntitlementValue:
    key: EntitlementKey
    kind: EntitlementKind
    integer_value: int | None = None
    boolean_value: bool | None = None

    def __post_init__(self) -> None:
        definition = ENTITLEMENT_REGISTRY.get(self.key)
        if definition is None or definition.kind is not self.kind:
            raise CatalogValidationError("La clé ou le type de droit est invalide.")
        if self.kind is EntitlementKind.LIMIT:
            if (
                not isinstance(self.integer_value, int)
                or isinstance(self.integer_value, bool)
                or self.integer_value < 0
            ):
                raise CatalogValidationError("Une limite doit être un entier positif ou nul.")
            if self.boolean_value is not None:
                raise CatalogValidationError("Une limite ne peut pas contenir de booléen.")
        elif not isinstance(self.boolean_value, bool) or self.integer_value is not None:
            raise CatalogValidationError("Un droit booléen doit contenir exactement un booléen.")


@dataclass(frozen=True, slots=True)
class EntitlementOverride:
    value: EntitlementValue
    state: OverrideState
    starts_at: datetime
    ends_at: datetime
    approved_by_is_creator: bool = False

    def __post_init__(self) -> None:
        if self.ends_at <= self.starts_at:
            raise CatalogValidationError("La fin d’une dérogation doit être postérieure à son début.")
        if self.state is OverrideState.ACTIVE and self.approved_by_is_creator:
            raise CatalogValidationError("Le créateur d’une dérogation ne peut pas l’approuver.")

    def applies_at(self, now: datetime) -> bool:
        return self.state is OverrideState.ACTIVE and self.starts_at <= now < self.ends_at


@dataclass(frozen=True, slots=True)
class EffectiveEntitlement:
    code: EntitlementDecisionCode
    key: EntitlementKey
    value: EntitlementValue | None
    source: str
    provenance: tuple[EntitlementProvenance, ...] = ()
    reason: EntitlementDecisionReason | None = None

    @property
    def allowed(self) -> bool:
        if self.value is None:
            return False
        if self.value.kind is EntitlementKind.SWITCH:
            return bool(self.value.boolean_value)
        return self.value.integer_value is not None and self.value.integer_value > 0


def resolve_effective_entitlement(
    *,
    key: EntitlementKey,
    contract_is_active: bool,
    plan_value: EntitlementValue | None,
    override: EntitlementOverride | None,
    now: datetime,
    safety_ceiling: EntitlementValue | None = None,
    contract_reason: EntitlementDecisionReason = EntitlementDecisionReason.CONTRACT_NOT_ACTIVE,
) -> EffectiveEntitlement:
    """Résout un droit sans jamais inventer de valeur en cas d'ambiguïté."""

    if not contract_is_active:
        return EffectiveEntitlement(
            EntitlementDecisionCode.DENY_UNKNOWN_CONTRACT,
            key,
            None,
            "none",
            (EntitlementProvenance(EntitlementProvenanceSource.CONTRACT, False, contract_reason),),
            contract_reason,
        )
    if plan_value is None or plan_value.key is not key:
        return EffectiveEntitlement(
            EntitlementDecisionCode.ENTITLEMENT_UNKNOWN,
            key,
            None,
            "none",
            (
                EntitlementProvenance(EntitlementProvenanceSource.CONTRACT, True),
                EntitlementProvenance(
                    EntitlementProvenanceSource.PLAN_VERSION,
                    False,
                    EntitlementDecisionReason.PLAN_ENTITLEMENT_MISSING,
                ),
            ),
            EntitlementDecisionReason.PLAN_ENTITLEMENT_MISSING,
        )

    provenance: list[EntitlementProvenance] = [
        EntitlementProvenance(EntitlementProvenanceSource.CONTRACT, True),
        EntitlementProvenance(
            EntitlementProvenanceSource.PLAN_VERSION, override is None or not override.applies_at(now)
        ),
    ]
    candidate = override.value if override is not None and override.applies_at(now) else plan_value
    source = "override" if candidate is not plan_value else "plan_version"
    if override is not None:
        override_reason = (
            EntitlementDecisionReason.OVERRIDE_EXPIRED
            if override.state is OverrideState.ACTIVE and now >= override.ends_at
            else None
        )
        provenance.append(
            EntitlementProvenance(
                EntitlementProvenanceSource.OVERRIDE,
                candidate is not plan_value,
                None if candidate is not plan_value else override_reason,
            )
        )
    if safety_ceiling is not None:
        if safety_ceiling.key is not key or safety_ceiling.kind is not candidate.kind:
            raise CatalogValidationError("Le plafond de sûreté n'est pas compatible avec le droit.")
        if candidate.kind is EntitlementKind.LIMIT:
            assert candidate.integer_value is not None and safety_ceiling.integer_value is not None
            if candidate.integer_value > safety_ceiling.integer_value:
                provenance.append(
                    EntitlementProvenance(
                        EntitlementProvenanceSource.SAFETY_CEILING,
                        False,
                        EntitlementDecisionReason.SAFETY_CEILING_EXCEEDED,
                    )
                )
                return EffectiveEntitlement(
                    EntitlementDecisionCode.SAFETY_CEILING_EXCEEDED,
                    key,
                    None,
                    source,
                    tuple(provenance),
                    EntitlementDecisionReason.SAFETY_CEILING_EXCEEDED,
                )
        elif candidate.boolean_value and not safety_ceiling.boolean_value:
            provenance.append(
                EntitlementProvenance(
                    EntitlementProvenanceSource.SAFETY_CEILING,
                    False,
                    EntitlementDecisionReason.SAFETY_CEILING_EXCEEDED,
                )
            )
            return EffectiveEntitlement(
                EntitlementDecisionCode.SAFETY_CEILING_EXCEEDED,
                key,
                None,
                source,
                tuple(provenance),
                EntitlementDecisionReason.SAFETY_CEILING_EXCEEDED,
            )
        provenance.append(EntitlementProvenance(EntitlementProvenanceSource.SAFETY_CEILING, True))
    code = (
        EntitlementDecisionCode.ALLOWED
        if (
            candidate.boolean_value
            if candidate.kind is EntitlementKind.SWITCH
            else candidate.integer_value and candidate.integer_value > 0
        )
        else EntitlementDecisionCode.ENTITLEMENT_DISABLED
    )
    return EffectiveEntitlement(code, key, candidate, source, tuple(provenance))
