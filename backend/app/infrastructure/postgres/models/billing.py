"""Schéma P5.3 : abonnements, commandes durables et preuves de paiement.

Les politiques RLS, les triggers de cohérence inter-table et les fonctions de
réservation restent des objets PostgreSQL gérés explicitement par la migration.
Ce module décrit les tables, contraintes et index afin qu'Alembic puisse détecter
une dérive de schéma sans proposer de supprimer le socle Billing.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    desc,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from .base import Base

_PROVIDER_CHECK = "provider IN ('simulated','stripe')"
_SUBSCRIPTION_STATES = "'pending_checkout','active','past_due','grace_period','suspended','canceling','canceled'"
_EVENT_TYPES = "'checkout.completed','subscription.snapshot','invoice.paid','invoice.payment_failed','refund.succeeded'"


class BillingCustomerModel(Base):
    __tablename__ = "billing_customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_billing_customers_org_id"),
        UniqueConstraint("organization_id", "provider", name="uq_billing_customers_org_provider"),
        UniqueConstraint("provider", "provider_customer_reference", name="uq_billing_customers_provider_reference"),
        CheckConstraint(_PROVIDER_CHECK, name="provider"),
        CheckConstraint("char_length(btrim(provider_customer_reference)) BETWEEN 1 AND 255", name="reference_nonempty"),
        CheckConstraint("version > 0", name="version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(16))
    provider_customer_reference: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class BillingCommandModel(Base):
    __tablename__ = "billing_commands"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_billing_commands_org_id"),
        UniqueConstraint("organization_id", "idempotency_key_digest", name="uq_billing_commands_org_key"),
        CheckConstraint("command_kind IN ('checkout','portal','refund')", name="kind"),
        CheckConstraint("idempotency_key_digest ~ '^[a-f0-9]{64}$'", name="key_digest"),
        CheckConstraint("request_fingerprint ~ '^[a-f0-9]{64}$'", name="fingerprint"),
        CheckConstraint("status IN ('reserved','succeeded','unknown','failed')", name="status"),
        CheckConstraint(
            "provider_command_reference IS NULL OR char_length(btrim(provider_command_reference)) BETWEEN 1 AND 255",
            name="provider_reference",
        ),
        CheckConstraint("version > 0", name="version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    command_kind: Mapped[str] = mapped_column(String(16))
    idempotency_key_digest: Mapped[str] = mapped_column(CHAR(64))
    request_fingerprint: Mapped[str] = mapped_column(CHAR(64))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'reserved'"))
    provider_command_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class BillingEventInboxModel(Base):
    __tablename__ = "billing_event_inbox"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_billing_event_inbox_provider_event"),
        CheckConstraint(_PROVIDER_CHECK, name="provider"),
        CheckConstraint(f"event_type IN ({_EVENT_TYPES})", name="type"),
        CheckConstraint(
            "char_length(btrim(provider_event_id)) BETWEEN 1 AND 255 "
            "AND char_length(btrim(provider_object_reference)) BETWEEN 1 AND 255",
            name="references_nonempty",
        ),
        CheckConstraint("payload_digest ~ '^[a-f0-9]{64}$'", name="digest"),
        CheckConstraint("signature_version > 0", name="signature_version"),
        CheckConstraint("jsonb_typeof(normalized_payload) = 'object'", name="payload_object"),
        CheckConstraint("octet_length(normalized_payload::text) <= 65536", name="payload_bounded"),
        CheckConstraint("status IN ('admitted','processing','processed','dead_letter','ignored')", name="status"),
        CheckConstraint("attempt_count BETWEEN 0 AND 8", name="attempts"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    provider: Mapped[str] = mapped_column(String(16))
    provider_event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(48))
    provider_object_reference: Mapped[str] = mapped_column(String(255))
    provider_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    payload_digest: Mapped[str] = mapped_column(CHAR(64))
    signature_version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    api_version: Mapped[str | None] = mapped_column(String(64))
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'admitted'"))
    attempt_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class SubscriptionModel(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_subscriptions_org_id"),
        UniqueConstraint("provider", "provider_subscription_reference", name="uq_subscriptions_provider_reference"),
        ForeignKeyConstraint(
            ["organization_id", "billing_customer_id"],
            ["billing_customers.organization_id", "billing_customers.id"],
            name="fk_subscriptions_organization_customer",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_PROVIDER_CHECK, name="provider"),
        CheckConstraint(
            "char_length(btrim(provider_subscription_reference)) BETWEEN 1 AND 255", name="reference_nonempty"
        ),
        CheckConstraint("currency IN ('CAD','USD','EUR','XAF')", name="currency"),
        CheckConstraint(f"state IN ({_SUBSCRIPTION_STATES})", name="state"),
        CheckConstraint("current_period_end > current_period_start", name="period"),
        CheckConstraint("provider_version > 0", name="provider_version_positive"),
        CheckConstraint("version > 0", name="version_positive"),
        Index(
            "uq_subscriptions_current_org",
            "organization_id",
            unique=True,
            postgresql_where=text(f"state IN ({_SUBSCRIPTION_STATES})"),
        ),
        Index("ix_subscriptions_org_state", "organization_id", "state", "current_period_end"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    billing_customer_id: Mapped[UUID] = mapped_column()
    provider: Mapped[str] = mapped_column(String(16))
    provider_subscription_reference: Mapped[str] = mapped_column(String(255))
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_versions.id", ondelete="RESTRICT"))
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(24), server_default=text("'pending_checkout'"))
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    provider_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider_version: Mapped[int] = mapped_column(BigInteger, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class BillingEventModel(Base):
    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_billing_events_org_id"),
        UniqueConstraint("inbox_id", name="uq_billing_events_inbox"),
        ForeignKeyConstraint(
            ["organization_id", "subscription_id"],
            ["subscriptions.organization_id", "subscriptions.id"],
            name="fk_billing_events_organization_subscription",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_PROVIDER_CHECK, name="provider"),
        CheckConstraint(f"event_type IN ({_EVENT_TYPES})", name="type"),
        CheckConstraint("char_length(btrim(provider_event_id)) BETWEEN 1 AND 255", name="reference_nonempty"),
        CheckConstraint("schema_version > 0", name="schema_version"),
        CheckConstraint("jsonb_typeof(normalized_payload) = 'object'", name="payload_object"),
        CheckConstraint("octet_length(normalized_payload::text) <= 65536", name="payload_bounded"),
        Index("ix_billing_events_org_occurred", "organization_id", desc("occurred_at")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    inbox_id: Mapped[UUID] = mapped_column(ForeignKey("billing_event_inbox.id", ondelete="RESTRICT"))
    subscription_id: Mapped[UUID | None] = mapped_column()
    provider: Mapped[str] = mapped_column(String(16))
    provider_event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(48))
    schema_version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class SubscriptionTransitionModel(Base):
    __tablename__ = "subscription_transitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "subscription_id"],
            ["subscriptions.organization_id", "subscriptions.id"],
            name="fk_subscription_transitions_organization_subscription",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_billing_event_id"],
            ["billing_events.organization_id", "billing_events.id"],
            name="fk_subscription_transitions_organization_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint(f"previous_state IN ({_SUBSCRIPTION_STATES})", name="previous_state"),
        CheckConstraint(f"next_state IN ({_SUBSCRIPTION_STATES})", name="next_state"),
        CheckConstraint("previous_state <> next_state", name="distinct_states"),
        CheckConstraint(
            "cause IN ('invoice_paid','checkout_abandoned','payment_failed','grace_period_started','grace_period_expired',"
            "'cancellation_scheduled','cancellation_revoked','cancellation_confirmed','new_checkout')",
            name="cause",
        ),
        Index("ix_subscription_transitions_org_subscription", "organization_id", "subscription_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    subscription_id: Mapped[UUID] = mapped_column()
    source_billing_event_id: Mapped[UUID | None] = mapped_column()
    previous_state: Mapped[str] = mapped_column(String(24))
    next_state: Mapped[str] = mapped_column(String(24))
    cause: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class BillingReconciliationRunModel(Base):
    __tablename__ = "billing_reconciliation_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_billing_reconciliation_runs_org_id"),
        CheckConstraint("run_kind IN ('incremental','exhaustive','manual')", name="kind"),
        CheckConstraint("status IN ('pending','running','completed','failed','blocked')", name="status"),
        CheckConstraint("window_ended_at > window_started_at", name="window"),
        CheckConstraint("completed_at IS NULL OR started_at IS NOT NULL", name="completion"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    run_kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    cursor_reference: Mapped[str | None] = mapped_column(String(255))
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class BillingReconciliationDifferenceModel(Base):
    __tablename__ = "billing_reconciliation_differences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "subscription_id"],
            ["subscriptions.organization_id", "subscriptions.id"],
            name="fk_billing_reconciliation_differences_organization_subscription",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "difference_code IN ('in_sync','local_stale','provider_stale','mapping_missing','currency_mismatch',"
            "'price_mismatch','unresolved')",
            name="code",
        ),
        CheckConstraint(
            "(local_reference IS NULL OR char_length(btrim(local_reference)) BETWEEN 1 AND 255) "
            "AND (provider_reference IS NULL OR char_length(btrim(provider_reference)) BETWEEN 1 AND 255)",
            name="references",
        ),
        Index("ix_billing_reconciliation_differences_org_run", "organization_id", "run_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("billing_reconciliation_runs.id", ondelete="RESTRICT"))
    subscription_id: Mapped[UUID | None] = mapped_column()
    difference_code: Mapped[str] = mapped_column(String(24))
    local_reference: Mapped[str | None] = mapped_column(String(255))
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class BillingRefundModel(Base):
    __tablename__ = "billing_refunds"
    __table_args__ = (
        UniqueConstraint("billing_command_id", name="uq_billing_refunds_command"),
        ForeignKeyConstraint(
            ["organization_id", "subscription_id"],
            ["subscriptions.organization_id", "subscriptions.id"],
            name="fk_billing_refunds_organization_subscription",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "billing_command_id"],
            ["billing_commands.organization_id", "billing_commands.id"],
            name="fk_billing_refunds_organization_command",
            ondelete="RESTRICT",
        ),
        CheckConstraint("char_length(btrim(provider_payment_reference)) BETWEEN 1 AND 255", name="payment_reference"),
        CheckConstraint(
            "provider_refund_reference IS NULL OR char_length(btrim(provider_refund_reference)) BETWEEN 1 AND 255",
            name="refund_reference",
        ),
        CheckConstraint("state IN ('requested','approved','rejected','succeeded','failed')", name="state"),
        CheckConstraint("decided_at IS NULL OR decided_at >= requested_at", name="decision"),
        CheckConstraint("completed_at IS NULL OR decided_at IS NOT NULL", name="completion"),
        CheckConstraint("version > 0", name="version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    subscription_id: Mapped[UUID] = mapped_column()
    billing_command_id: Mapped[UUID] = mapped_column()
    provider_payment_reference: Mapped[str] = mapped_column(String(255))
    provider_refund_reference: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(16), server_default=text("'requested'"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
