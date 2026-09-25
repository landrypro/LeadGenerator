from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProviderConnectorContractModel(Base):
    __tablename__ = "provider_connector_contracts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "creator_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_connector_contracts_org_id"),
        UniqueConstraint("organization_id", "provider_id", "connector_code", name="uq_connector_contracts_provider"),
        CheckConstraint("connector_code = 'meta_lead_ads'", name="ck_connector_contract_code"),
        CheckConstraint(
            "status IN ('draft','pending_review','approved','suspended','revoked','expired')",
            name="ck_connector_contract_status",
        ),
        CheckConstraint(
            "jsonb_typeof(requested_permissions) = 'array' AND jsonb_typeof(approved_permissions) = 'array'",
            name="ck_connector_contract_permissions",
        ),
        CheckConstraint("version > 0", name="ck_connector_contract_version"),
        Index("ix_connector_contracts_org_status", "organization_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    provider_id: Mapped[UUID] = mapped_column()
    connector_code: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'draft'"))
    evidence_ref: Mapped[str | None] = mapped_column(String(256))
    meta_app_reference: Mapped[str | None] = mapped_column(String(128))
    requested_permissions: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    approved_permissions: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    creator_membership_id: Mapped[UUID] = mapped_column()
    review_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewer_membership_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class ProviderConnectorBindingModel(Base):
    __tablename__ = "provider_connector_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "contract_id"],
            ["provider_connector_contracts.organization_id", "provider_connector_contracts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "acquisition_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_connector_bindings_org_id"),
        UniqueConstraint("form_fingerprint", name="uq_connector_bindings_form_global"),
        CheckConstraint("status IN ('draft','active','disabled')", name="ck_connector_binding_status"),
        CheckConstraint(
            "form_fingerprint ~ '^[a-f0-9]{64}$' AND (page_fingerprint IS NULL OR page_fingerprint ~ '^[a-f0-9]{64}$')",
            name="ck_connector_binding_fingerprint",
        ),
        CheckConstraint(
            "email_permission_status IN ('unknown','allowed') AND phone_permission_status IN ('unknown','allowed')",
            name="ck_connector_binding_permission",
        ),
        CheckConstraint("version > 0", name="ck_connector_binding_version"),
        Index("ix_connector_bindings_org_status", "organization_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    contract_id: Mapped[UUID] = mapped_column()
    acquisition_id: Mapped[UUID] = mapped_column()
    form_fingerprint: Mapped[str] = mapped_column(String(64))
    page_fingerprint: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'draft'"))
    allow_full_name: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    allow_email: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    allow_phone: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    email_permission_status: Mapped[str] = mapped_column(String(16), server_default=text("'unknown'"))
    phone_permission_status: Mapped[str] = mapped_column(String(16), server_default=text("'unknown'"))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class ConnectorIngestionModel(Base):
    __tablename__ = "connector_ingestions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "binding_id"],
            ["provider_connector_bindings.organization_id", "provider_connector_bindings.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(
            ["organization_id", "actor_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_connector_ingestions_org_id"),
        UniqueConstraint("organization_id", "binding_id", "lead_fingerprint", name="uq_connector_ingestions_lead"),
        UniqueConstraint("job_id", name="uq_connector_ingestions_job"),
        CheckConstraint("lead_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_connector_ingestions_fingerprint"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','quarantined','failed','revoked')",
            name="ck_connector_ingestions_status",
        ),
        CheckConstraint("attempt_count >= 0 AND version > 0", name="ck_connector_ingestions_version"),
        Index("ix_connector_ingestions_org_status", "organization_id", "status", "received_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    binding_id: Mapped[UUID] = mapped_column()
    job_id: Mapped[UUID | None] = mapped_column()
    lead_fingerprint: Mapped[str] = mapped_column(String(64))
    lead_reference_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_membership_id: Mapped[UUID] = mapped_column()
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'queued'"))
    attempt_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class ConnectorIngestionOutcomeModel(Base):
    __tablename__ = "connector_ingestion_outcomes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "ingestion_id"],
            ["connector_ingestions.organization_id", "connector_ingestions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "contact_id"], ["contacts.organization_id", "contacts.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "ingestion_id", name="uq_connector_outcomes_ingestion"),
        CheckConstraint(
            "result_code IN ('imported','quarantined','failed','authorization_revoked')",
            name="ck_connector_outcomes_result",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    ingestion_id: Mapped[UUID] = mapped_column()
    prospect_id: Mapped[UUID | None] = mapped_column()
    contact_id: Mapped[UUID | None] = mapped_column()
    provenance_id: Mapped[UUID | None] = mapped_column()
    result_code: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
