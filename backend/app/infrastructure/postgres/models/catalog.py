"""Schéma P5.2 : catalogue global et droits isolés par organisation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    column,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from .base import Base


class PlanCatalogModel(Base):
    __tablename__ = "plan_catalog"
    __table_args__ = (
        CheckConstraint("code IN ('freemium','starter','business','custom')", name="code_allowed"),
        CheckConstraint("state IN ('draft','published','retired')", name="state_allowed"),
        CheckConstraint("display_order >= 0", name="display_order_nonnegative"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("code", name="uq_plan_catalog_code"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16), server_default=text("'draft'"))
    display_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class PlanVersionModel(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (
        CheckConstraint("state IN ('draft','published','superseded','retired')", name="state_allowed"),
        CheckConstraint("currency IN ('CAD','USD','EUR','XAF')", name="currency_allowed"),
        CheckConstraint("billing_cycle IN ('monthly','annual','custom_contract')", name="cycle_allowed"),
        CheckConstraint("amount_excluding_tax_minor >= 0", name="amount_nonnegative"),
        CheckConstraint("version_number > 0", name="number_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("effective_until IS NULL OR effective_until > effective_from", name="effective_range"),
        CheckConstraint(
            "state <> 'published' OR (approved_by_user_id IS NOT NULL "
            "AND approved_by_user_id <> created_by_user_id AND published_at IS NOT NULL)",
            name="published_approval",
        ),
        UniqueConstraint("plan_id", "version_number", name="uq_plan_versions_plan_number"),
        Index("ix_plan_versions_plan_state", "plan_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plan_catalog.id", ondelete="RESTRICT"))
    version_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), server_default=text("'draft'"))
    currency: Mapped[str] = mapped_column(String(3))
    billing_cycle: Mapped[str] = mapped_column(String(32))
    amount_excluding_tax_minor: Mapped[int] = mapped_column(BigInteger)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class PlanEntitlementModel(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (
        CheckConstraint(
            "entitlement_key IN ('seats.active_members.max','seats.pending_invitations.max','prospects.active.max',"
            "'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',"
            "'automation.prepare.enabled','automation.execute.enabled')",
            name="key_allowed",
        ),
        CheckConstraint("value_kind IN ('limit','switch')", name="kind_allowed"),
        CheckConstraint(
            "(value_kind = 'limit' AND integer_value IS NOT NULL AND integer_value >= 0 AND boolean_value IS NULL) "
            "OR (value_kind = 'switch' AND boolean_value IS NOT NULL AND integer_value IS NULL)",
            name="typed_value",
        ),
        CheckConstraint(
            "(entitlement_key='seats.active_members.max' AND unit='seat' AND scope='organization') OR "
            "(entitlement_key='seats.pending_invitations.max' AND unit='reserved_seat' AND scope='organization') OR "
            "(entitlement_key='prospects.active.max' AND unit='prospect' AND scope='organization') OR "
            "(entitlement_key='exports.monthly.max' AND unit='export' AND scope='period') OR "
            "(entitlement_key='imports.rows_per_run.max' AND unit='row' AND scope='run') OR "
            "(entitlement_key IN ('google.paid_calls.enabled','automation.prepare.enabled','automation.execute.enabled') "
            "AND unit='boolean' AND scope='organization')",
            name="key_unit_scope",
        ),
        UniqueConstraint("plan_version_id", "entitlement_key", name="uq_plan_entitlements_version_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_versions.id", ondelete="CASCADE"))
    entitlement_key: Mapped[str] = mapped_column(String(64))
    value_kind: Mapped[str] = mapped_column(String(16))
    integer_value: Mapped[int | None] = mapped_column(BigInteger)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    unit: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class OrganizationPlanContractModel(Base):
    __tablename__ = "organization_plan_contracts"
    __table_args__ = (
        CheckConstraint("state IN ('pending','active','suspended','ended')", name="state_allowed"),
        CheckConstraint("currency IN ('CAD','USD','EUR','XAF')", name="currency_allowed"),
        CheckConstraint("effective_until IS NULL OR effective_until > effective_from", name="effective_range"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "id", name="uq_organization_plan_contracts_org_id"),
        Index("ix_organization_plan_contracts_org_state", "organization_id", "state", "effective_from"),
        Index(
            "uq_organization_plan_contracts_current",
            "organization_id",
            unique=True,
            postgresql_where=text("state IN ('pending','active','suspended')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_versions.id", ondelete="RESTRICT"))
    state: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    currency: Mapped[str] = mapped_column(String(3))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class PlanContractOverrideModel(Base):
    __tablename__ = "plan_contract_overrides"
    __table_args__ = (
        CheckConstraint("state IN ('pending_approval','active','expired','revoked')", name="state_allowed"),
        CheckConstraint(
            "entitlement_key IN ('seats.active_members.max','seats.pending_invitations.max','prospects.active.max',"
            "'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',"
            "'automation.prepare.enabled','automation.execute.enabled')",
            name="key_allowed",
        ),
        CheckConstraint("value_kind IN ('limit','switch')", name="kind_allowed"),
        CheckConstraint(
            "(value_kind = 'limit' AND integer_value IS NOT NULL AND integer_value >= 0 AND boolean_value IS NULL) "
            "OR (value_kind = 'switch' AND boolean_value IS NOT NULL AND integer_value IS NULL)",
            name="typed_value",
        ),
        CheckConstraint("char_length(justification) BETWEEN 1 AND 512", name="justification_length"),
        CheckConstraint("ends_at > starts_at", name="active_range"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "id", name="uq_plan_contract_overrides_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "contract_id"],
            ["organization_plan_contracts.organization_id", "organization_plan_contracts.id"],
            ondelete="RESTRICT",
        ),
        ExcludeConstraint(
            ("organization_id", "="),
            ("entitlement_key", "="),
            (func.tstzrange(column("starts_at"), column("ends_at"), "[)"), "&&"),
            where=text("state IN ('pending_approval','active')"),
            name="ex_plan_contract_overrides_no_overlap",
        ),
        Index("ix_plan_contract_overrides_org_contract", "organization_id", "contract_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    contract_id: Mapped[UUID] = mapped_column()
    entitlement_key: Mapped[str] = mapped_column(String(64))
    value_kind: Mapped[str] = mapped_column(String(16))
    integer_value: Mapped[int | None] = mapped_column(BigInteger)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    state: Mapped[str] = mapped_column(String(32), server_default=text("'pending_approval'"))
    justification: Mapped[str] = mapped_column(String(512))
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class EntitlementSafetyCeilingModel(Base):
    """Plafond technique global, jamais une source commerciale ou locataire."""

    __tablename__ = "entitlement_safety_ceilings"
    __table_args__ = (
        CheckConstraint(
            "entitlement_key IN ('seats.active_members.max','seats.pending_invitations.max','prospects.active.max',"
            "'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',"
            "'automation.prepare.enabled','automation.execute.enabled')",
            name="key_allowed",
        ),
        CheckConstraint("value_kind IN ('limit','switch')", name="kind_allowed"),
        CheckConstraint(
            "(value_kind = 'limit' AND integer_value IS NOT NULL AND integer_value >= 0 AND boolean_value IS NULL) "
            "OR (value_kind = 'switch' AND boolean_value IS NOT NULL AND integer_value IS NULL)",
            name="typed_value",
        ),
    )

    entitlement_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_kind: Mapped[str] = mapped_column(String(16))
    integer_value: Mapped[int | None] = mapped_column(BigInteger)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class CatalogMutationOperationModel(Base):
    __tablename__ = "catalog_mutation_operations"
    __table_args__ = (
        CheckConstraint(
            "command IN ('create_plan','create_plan_version','publish_plan_version','attach_contract','change_contract_state',"
            "'propose_contract_override','approve_contract_override','revoke_contract_override')",
            name="command_allowed",
        ),
    )

    operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    command: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    response: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
