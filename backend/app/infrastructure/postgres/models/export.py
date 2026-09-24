"""Phase 4.3 private export registry and explicit source rights."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ExportRequestModel(Base):
    __tablename__ = "export_requests"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_export_requests_org_id"),
        UniqueConstraint("organization_id", "idempotency_digest", name="uq_export_requests_idempotency"),
        UniqueConstraint("job_id", name="uq_export_requests_job"),
        ForeignKeyConstraint(
            ["organization_id", "requester_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="CASCADE"),
        CheckConstraint(
            "dataset IN ('prospects','contacts','contact_channels','activities','tasks','opportunities')",
            name="ck_export_dataset",
        ),
        CheckConstraint("schema_code = 'crm_csv_v1'", name="ck_export_schema"),
        CheckConstraint("scope IN ('self','organization')", name="ck_export_scope"),
        CheckConstraint(
            "status IN ('queued','running','ready','failed','cancelled','expired')", name="ck_export_status"
        ),
        CheckConstraint(
            "jsonb_typeof(filters) = 'object' AND jsonb_typeof(columns) = 'array'", name="ck_export_contract"
        ),
        Index("ix_export_requests_list", "organization_id", "requester_user_id", "created_at", "id"),
        Index("ix_export_requests_org_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    requester_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    requester_membership_id: Mapped[UUID] = mapped_column()
    job_id: Mapped[UUID | None] = mapped_column()
    dataset: Mapped[str] = mapped_column(String(32))
    schema_code: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(16))
    filters: Mapped[dict[str, str]] = mapped_column(JSONB)
    columns: Mapped[list[str]] = mapped_column(JSONB)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    idempotency_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))


class ExportArtifactModel(Base):
    __tablename__ = "export_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "export_id"],
            ["export_requests.organization_id", "export_requests.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("byte_size BETWEEN 1 AND 52428800", name="ck_export_artifact_size"),
        CheckConstraint("row_count BETWEEN 0 AND 50000 AND omitted_count >= 0", name="ck_export_artifact_counts"),
        CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="ck_export_artifact_sha"),
        CheckConstraint("expires_at > published_at", name="ck_export_artifact_expiry"),
        Index("ix_export_artifacts_expiry", "expires_at", "deleted_at"),
    )

    export_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column()
    file_ref: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    omitted_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceExportRuleModel(Base):
    __tablename__ = "source_export_rules"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_source_export_rules_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "acquisition_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("(acquisition_id IS NULL) <> (provider_id IS NULL)", name="ck_export_rule_target"),
        CheckConstraint("status IN ('allowed','denied','unknown')", name="ck_export_rule_status"),
        CheckConstraint("jsonb_typeof(field_codes) = 'array'", name="ck_export_rule_fields"),
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_export_rule_validity"),
        CheckConstraint("version > 0", name="ck_export_rule_version"),
        Index("ix_source_export_rules_acquisition", "organization_id", "acquisition_id", "data_category"),
        Index("ix_source_export_rules_provider", "organization_id", "provider_id", "data_category"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    acquisition_id: Mapped[UUID | None] = mapped_column()
    provider_id: Mapped[UUID | None] = mapped_column()
    data_category: Mapped[str] = mapped_column(String(32))
    field_codes: Mapped[list[str]] = mapped_column(JSONB)
    purpose: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_ref: Mapped[str] = mapped_column(String(256))
    attested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    attested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
