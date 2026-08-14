from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SourceProviderModel(Base):
    __tablename__ = "source_providers"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('csv', 'facebook', 'linkedin', 'open_data', 'api', 'other')", name="source_kind_allowed"
        ),
        CheckConstraint("char_length(label) BETWEEN 1 AND 160", name="label_length"),
        CheckConstraint("status IN ('active', 'disabled')", name="status_allowed"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "id"),
        Index("ix_source_providers_organization_source_kind", "organization_id", "source_kind"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    source_kind: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class AcquisitionRecordModel(Base):
    __tablename__ = "acquisition_records"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('google_maps', 'csv', 'facebook', 'linkedin', 'open_data', 'api', 'manual', 'other')",
            name="source_kind_allowed",
        ),
        CheckConstraint("char_length(source_label) BETWEEN 1 AND 160", name="source_label_length"),
        CheckConstraint("char_length(purpose) BETWEEN 1 AND 64", name="purpose_length"),
        CheckConstraint("status IN ('declared', 'reviewed', 'rejected')", name="status_allowed"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_acquisition_records_organization_source_obtained", "organization_id", "source_kind", "obtained_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    source_kind: Mapped[str] = mapped_column(String(32))
    source_label: Mapped[str] = mapped_column(String(160))
    provider_id: Mapped[UUID | None] = mapped_column()
    purpose: Mapped[str] = mapped_column(String(64))
    territory: Mapped[str | None] = mapped_column(String(120))
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    declared_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'declared'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class ProvenanceRecordModel(Base):
    __tablename__ = "provenance_records"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('google_maps', 'manual', 'csv', 'facebook', 'linkedin', 'open_data', 'api', 'other')",
            name="source_kind_allowed",
        ),
        CheckConstraint("char_length(source_label) BETWEEN 1 AND 160", name="source_label_length"),
        CheckConstraint(
            "evidence_ref IS NULL OR char_length(evidence_ref) BETWEEN 1 AND 256", name="evidence_ref_length"
        ),
        CheckConstraint("char_length(purpose) BETWEEN 1 AND 64", name="purpose_length"),
        CheckConstraint("territory IS NULL OR char_length(territory) BETWEEN 1 AND 120", name="territory_length"),
        CheckConstraint("verified_at IS NULL OR verified_at >= obtained_at", name="verification_after_obtained"),
        ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_provenance_records_organization_source_obtained", "organization_id", "source_kind", "obtained_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    source_kind: Mapped[str] = mapped_column(String(32))
    source_label: Mapped[str] = mapped_column(String(160))
    provider_id: Mapped[UUID | None] = mapped_column()
    evidence_ref: Mapped[str | None] = mapped_column(String(256))
    purpose: Mapped[str] = mapped_column(String(64))
    territory: Mapped[str | None] = mapped_column(String(120))
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class ProspectModel(Base):
    __tablename__ = "prospects"
    __table_args__ = (
        CheckConstraint(
            "google_place_id IS NULL OR char_length(google_place_id) BETWEEN 1 AND 255", name="google_place_id_length"
        ),
        CheckConstraint("char_length(internal_alias) BETWEEN 1 AND 160", name="internal_alias_length"),
        CheckConstraint(
            "origin IN ('google_place', 'manual', 'import', 'connector', 'open_data')", name="origin_allowed"
        ),
        CheckConstraint("char_length(source_label) BETWEEN 1 AND 160", name="source_label_length"),
        CheckConstraint(
            "stage_code IN ('new', 'qualified', 'contacted', 'proposal_sent', 'won', 'lost', 'archived')",
            name="stage_code_allowed",
        ),
        CheckConstraint("priority BETWEEN 0 AND 5", name="priority_range"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "acquisition_record_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "owner_id"], ["memberships.organization_id", "memberships.id"], ondelete="RESTRICT"
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_prospects_organization_stage", "organization_id", "stage_code"),
        Index("ix_prospects_organization_owner", "organization_id", "owner_id"),
        Index("ix_prospects_organization_retention_review", "organization_id", "retention_review_at"),
        Index(
            "uq_prospects_active_google_place",
            "organization_id",
            "google_place_id",
            unique=True,
            postgresql_where=text("google_place_id IS NOT NULL AND archived_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    google_place_id: Mapped[str | None] = mapped_column(String(255))
    internal_alias: Mapped[str] = mapped_column(String(160))
    origin: Mapped[str] = mapped_column(String(32))
    source_label: Mapped[str] = mapped_column(String(160))
    acquisition_record_id: Mapped[UUID | None] = mapped_column()
    owner_id: Mapped[UUID | None] = mapped_column()
    stage_code: Mapped[str] = mapped_column(String(32), server_default=text("'new'"))
    priority: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    retention_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContactModel(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 160", name="display_name_length"),
        CheckConstraint("role_label IS NULL OR char_length(role_label) BETWEEN 1 AND 120", name="role_label_length"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_contacts_organization_prospect", "organization_id", "prospect_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    prospect_id: Mapped[UUID] = mapped_column()
    display_name: Mapped[str] = mapped_column(String(160))
    role_label: Mapped[str | None] = mapped_column(String(120))
    provenance_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContactChannelModel(Base):
    __tablename__ = "contact_channels"
    __table_args__ = (
        CheckConstraint("(prospect_id IS NULL) <> (contact_id IS NULL)", name="target_xor"),
        CheckConstraint(
            "channel_type IN ('email', 'phone', 'linkedin', 'facebook', 'other')", name="channel_type_allowed"
        ),
        CheckConstraint("char_length(value) BETWEEN 1 AND 512", name="value_length"),
        CheckConstraint("char_length(value_normalized) BETWEEN 1 AND 512", name="value_normalized_length"),
        CheckConstraint("char_length(purpose) BETWEEN 1 AND 64", name="purpose_length"),
        CheckConstraint(
            "verified_at IS NULL OR obtained_at IS NULL OR verified_at >= obtained_at",
            name="verification_after_obtained",
        ),
        CheckConstraint("version > 0", name="version_positive"),
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
        UniqueConstraint("organization_id", "id"),
        Index(
            "ix_contact_channels_organization_type_normalized", "organization_id", "channel_type", "value_normalized"
        ),
        Index("ix_contact_channels_organization_prospect", "organization_id", "prospect_id"),
        Index("ix_contact_channels_organization_contact", "organization_id", "contact_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    prospect_id: Mapped[UUID | None] = mapped_column()
    contact_id: Mapped[UUID | None] = mapped_column()
    channel_type: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(Text)
    value_normalized: Mapped[str] = mapped_column(String(512))
    provenance_id: Mapped[UUID] = mapped_column()
    purpose: Mapped[str] = mapped_column(String(64))
    obtained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContactPermissionModel(Base):
    __tablename__ = "contact_permissions"
    __table_args__ = (
        CheckConstraint("status IN ('unknown', 'allowed', 'do_not_contact', 'opted_out')", name="status_allowed"),
        CheckConstraint("reason IS NULL OR char_length(reason) BETWEEN 1 AND 160", name="reason_length"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "channel_id"],
            ["contact_channels.organization_id", "contact_channels.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_contact_permissions_organization_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    channel_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), server_default=text("'unknown'"))
    provenance_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(160))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
