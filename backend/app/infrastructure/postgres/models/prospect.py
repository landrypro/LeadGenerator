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
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SourceProviderModel(Base):
    __tablename__ = "source_providers"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('csv', 'facebook', 'linkedin', 'open_data', 'api', 'other')", name="source_kind_allowed"
        ),
        CheckConstraint("char_length(label) BETWEEN 1 AND 160", name="label_length"),
        CheckConstraint("status IN ('draft', 'active', 'suspended', 'retired')", name="status_allowed"),
        CheckConstraint(
            "allowed_territories IS NOT NULL AND jsonb_typeof(allowed_territories) = 'array'",
            name="allowed_territories_array",
        ),
        CheckConstraint(
            "allowed_purposes IS NOT NULL AND jsonb_typeof(allowed_purposes) = 'array'",
            name="allowed_purposes_array",
        ),
        CheckConstraint(
            "allowed_data_categories IS NOT NULL AND jsonb_typeof(allowed_data_categories) = 'array'",
            name="allowed_data_categories_array",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "id", name="uq_source_providers_organization_id_id"),
        Index("ix_source_providers_organization_source_kind", "organization_id", "source_kind"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    source_kind: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'draft'"))
    terms_reference: Mapped[str | None] = mapped_column(String(256))
    terms_url: Mapped[str | None] = mapped_column(String(256))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allowed_territories: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    allowed_purposes: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    allowed_data_categories: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    rights_attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rights_attested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
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
        CheckConstraint("status IN ('pending_review', 'approved', 'quarantined', 'rejected')", name="status_allowed"),
        CheckConstraint(
            "data_categories IS NOT NULL AND jsonb_typeof(data_categories) = 'array'", name="data_categories_array"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_acquisition_records_organization_id_id"),
        Index("ix_acquisition_records_organization_source_obtained", "organization_id", "source_kind", "obtained_at"),
        Index(
            "uq_acquisition_records_declaration_idempotency",
            "organization_id",
            "declaration_idempotency_key",
            unique=True,
            postgresql_where=text("declaration_idempotency_key IS NOT NULL"),
        ),
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
    status: Mapped[str] = mapped_column(String(16), server_default=text("'pending_review'"))
    external_reference: Mapped[str | None] = mapped_column(String(128))
    data_categories: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    decision_reason_code: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    declaration_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    declaration_fingerprint: Mapped[str | None] = mapped_column(String(128))
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
        ForeignKeyConstraint(
            ["organization_id", "acquisition_record_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
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
    acquisition_record_id: Mapped[UUID | None] = mapped_column()
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
            "stage_code IN ('new', 'qualifying', 'qualified', 'contacted', 'opportunity', 'proposal_sent', 'negotiation', 'won', 'lost', 'archived')",
            name="stage_code_allowed",
        ),
        CheckConstraint("priority BETWEEN 0 AND 5", name="priority_range"),
        CheckConstraint(
            "segment_code IN ('unspecified', 'micro', 'small', 'medium', 'enterprise')", name="segment_code_allowed"
        ),
        CheckConstraint(
            "size_band IN ('unknown', 'solo', '2_10', '11_50', '51_200', '201_plus')", name="size_band_allowed"
        ),
        CheckConstraint("country_code IS NULL OR country_code ~ '^[A-Z]{2}$'", name="country_code_format"),
        CheckConstraint(
            "tags IS NOT NULL AND jsonb_typeof(tags) = 'array' AND jsonb_array_length(tags) <= 20", name="tags_array"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "acquisition_record_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "owner_id"], ["memberships.organization_id", "memberships.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "profile_provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_prospects_organization_stage", "organization_id", "stage_code"),
        Index("ix_prospects_organization_owner", "organization_id", "owner_id"),
        Index("ix_prospects_organization_retention_review", "organization_id", "retention_review_at"),
        Index("ix_prospects_organization_archived", "organization_id", "archived_at"),
        Index("ix_prospects_organization_updated", "organization_id", "updated_at"),
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
    stage_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    archive_reason_code: Mapped[str | None] = mapped_column(String(64))
    profile_provenance_id: Mapped[UUID | None] = mapped_column()
    industry_label: Mapped[str | None] = mapped_column(String(120))
    segment_code: Mapped[str] = mapped_column(String(16), server_default=text("'unspecified'"))
    size_band: Mapped[str] = mapped_column(String(16), server_default=text("'unknown'"))
    address_line_1: Mapped[str | None] = mapped_column(String(160))
    address_line_2: Mapped[str | None] = mapped_column(String(160))
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(32))
    country_code: Mapped[str | None] = mapped_column(String(2))
    tags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class PipelineStageSettingModel(Base):
    __tablename__ = "pipeline_stage_settings"
    __table_args__ = (
        CheckConstraint(
            "stage_code IN ('new', 'qualifying', 'qualified', 'contacted', 'opportunity', 'proposal_sent', 'negotiation', 'won', 'lost')",
            name="stage_code_allowed",
        ),
        CheckConstraint("position BETWEEN 1 AND 9", name="position_range"),
        CheckConstraint("char_length(color_token) BETWEEN 1 AND 32", name="color_token_length"),
        CheckConstraint("labels IS NOT NULL AND jsonb_typeof(labels) = 'object'", name="labels_object"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "stage_code", name="uq_pipeline_stage_settings_organization_stage"),
        UniqueConstraint("organization_id", "position", name="uq_pipeline_stage_settings_organization_position"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    stage_code: Mapped[str] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(Integer)
    color_token: Mapped[str] = mapped_column(String(32))
    labels: Mapped[dict[str, str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class ProspectStageTransitionModel(Base):
    __tablename__ = "prospect_stage_transitions"
    __table_args__ = (
        CheckConstraint(
            "from_stage IN ('new', 'qualifying', 'qualified', 'contacted', 'opportunity', 'proposal_sent', 'negotiation', 'won', 'lost')",
            name="from_stage_allowed",
        ),
        CheckConstraint(
            "to_stage IN ('new', 'qualifying', 'qualified', 'contacted', 'opportunity', 'proposal_sent', 'negotiation', 'won', 'lost')",
            name="to_stage_allowed",
        ),
        CheckConstraint("from_stage <> to_stage", name="stage_changed"),
        CheckConstraint("from_version > 0 AND resulting_version > from_version", name="version_sequence"),
        CheckConstraint("reason_note IS NULL OR char_length(reason_note) BETWEEN 1 AND 500", name="reason_note_length"),
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        UniqueConstraint("organization_id", "id", name="uq_prospect_stage_transitions_organization_id_id"),
        UniqueConstraint(
            "organization_id",
            "prospect_id",
            "idempotency_key",
            name="uq_prospect_stage_transitions_idempotency",
        ),
        Index(
            "ix_prospect_stage_transitions_organization_prospect_occurred",
            "organization_id",
            "prospect_id",
            "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    prospect_id: Mapped[UUID] = mapped_column()
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    from_stage: Mapped[str] = mapped_column(String(32))
    to_stage: Mapped[str] = mapped_column(String(32))
    from_version: Mapped[int] = mapped_column(Integer)
    resulting_version: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    reason_note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    command_fingerprint: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProspectActivityModel(Base):
    __tablename__ = "prospect_activities"
    __table_args__ = (
        CheckConstraint("activity_type IN ('note', 'call', 'email', 'meeting')", name="activity_type_allowed"),
        CheckConstraint("direction IN ('internal', 'inbound', 'outbound')", name="direction_allowed"),
        CheckConstraint("char_length(summary) BETWEEN 1 AND 160", name="summary_length"),
        CheckConstraint("note IS NULL OR char_length(note) BETWEEN 1 AND 4000", name="note_length"),
        CheckConstraint(
            "permission_snapshot IN ('unknown', 'allowed', 'restricted', 'not_applicable')",
            name="permission_snapshot_allowed",
        ),
        CheckConstraint("(correction_of_activity_id IS NULL) = (correction_reason IS NULL)", name="correction_pair"),
        CheckConstraint(
            "correction_reason IS NULL OR char_length(correction_reason) BETWEEN 1 AND 500",
            name="correction_reason_length",
        ),
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "contact_id"], ["contacts.organization_id", "contacts.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "contact_channel_id"],
            ["contact_channels.organization_id", "contact_channels.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "correction_of_activity_id"],
            ["prospect_activities.organization_id", "prospect_activities.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_prospect_activities_organization_id_id"),
        Index("ix_prospect_activities_organization_prospect_occurred", "organization_id", "prospect_id", "occurred_at"),
        Index("ix_prospect_activities_organization_actor_occurred", "organization_id", "actor_id", "occurred_at"),
        Index(
            "uq_prospect_activities_idempotency",
            "organization_id",
            "prospect_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    prospect_id: Mapped[UUID] = mapped_column()
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    activity_type: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contact_id: Mapped[UUID | None] = mapped_column()
    contact_channel_id: Mapped[UUID | None] = mapped_column()
    permission_snapshot: Mapped[str] = mapped_column(String(32), server_default=text("'not_applicable'"))
    correction_of_activity_id: Mapped[UUID | None] = mapped_column()
    correction_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    command_fingerprint: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class ProspectTaskModel(Base):
    __tablename__ = "prospect_tasks"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 160", name="title_length"),
        CheckConstraint(
            "description IS NULL OR char_length(description) BETWEEN 1 AND 2000", name="description_length"
        ),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="priority_allowed"),
        CheckConstraint("status IN ('open', 'completed', 'cancelled')", name="status_allowed"),
        CheckConstraint("reminder_at IS NULL OR reminder_at <= due_at", name="reminder_before_due"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_prospect_tasks_organization_id_id"),
        Index("ix_prospect_tasks_organization_prospect_due", "organization_id", "prospect_id", "due_at"),
        Index(
            "ix_prospect_tasks_organization_assignee_status_due",
            "organization_id",
            "assigned_membership_id",
            "status",
            "due_at",
        ),
        Index(
            "uq_prospect_tasks_idempotency",
            "organization_id",
            "prospect_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    prospect_id: Mapped[UUID] = mapped_column()
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_membership_id: Mapped[UUID | None] = mapped_column()
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), server_default=text("'normal'"))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'open'"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    command_fingerprint: Mapped[str | None] = mapped_column(String(128))


class ProspectTaskEventModel(Base):
    __tablename__ = "prospect_task_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'updated', 'completed', 'cancelled', 'reopened', 'reminder_acknowledged', 'reminder_snoozed')",
            name="event_type_allowed",
        ),
        CheckConstraint("resulting_status IN ('open', 'completed', 'cancelled')", name="resulting_status_allowed"),
        CheckConstraint("resulting_version > 0", name="resulting_version_positive"),
        CheckConstraint(
            "changed_fields IS NOT NULL AND jsonb_typeof(changed_fields) = 'object'", name="changed_fields_object"
        ),
        CheckConstraint("reason IS NULL OR char_length(reason) BETWEEN 1 AND 500", name="reason_length"),
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["organization_id", "task_id"], ["prospect_tasks.organization_id", "prospect_tasks.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("organization_id", "id", name="uq_prospect_task_events_organization_id_id"),
        Index("ix_prospect_task_events_organization_task_occurred", "organization_id", "task_id", "occurred_at"),
        Index(
            "uq_prospect_task_events_idempotency",
            "organization_id",
            "task_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    prospect_id: Mapped[UUID] = mapped_column()
    task_id: Mapped[UUID] = mapped_column()
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(32))
    resulting_status: Mapped[str] = mapped_column(String(16))
    resulting_version: Mapped[int] = mapped_column(Integer)
    changed_fields: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    reason: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    command_fingerprint: Mapped[str | None] = mapped_column(String(128))


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
    archived_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    archive_reason_code: Mapped[str | None] = mapped_column(String(64))


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
    archived_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    archive_reason_code: Mapped[str | None] = mapped_column(String(64))


class ContactPermissionModel(Base):
    __tablename__ = "contact_permissions"
    __table_args__ = (
        CheckConstraint("status IN ('unknown', 'allowed', 'do_not_contact', 'opted_out')", name="status_allowed"),
        CheckConstraint(
            "legal_basis_code IS NULL OR legal_basis_code IN "
            "('consent', 'contract', 'legitimate_interest', 'customer_request', 'other')",
            name="legal_basis_code_allowed",
        ),
        CheckConstraint("reason IS NULL OR char_length(reason) BETWEEN 1 AND 160", name="reason_length"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="validity_order"
        ),
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
        UniqueConstraint("organization_id", "channel_id"),
        Index("ix_contact_permissions_organization_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    channel_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), server_default=text("'unknown'"))
    legal_basis_code: Mapped[str | None] = mapped_column(String(64))
    provenance_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(160))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class RetentionPolicyModel(Base):
    __tablename__ = "retention_policies"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('prospect', 'contact', 'contact_channel', 'acquisition_record', "
            "'provenance_record', 'import_declaration')",
            name="resource_type_allowed",
        ),
        CheckConstraint("char_length(policy_code) BETWEEN 1 AND 64", name="policy_code_length"),
        CheckConstraint("char_length(label) BETWEEN 1 AND 160", name="label_length"),
        CheckConstraint("status IN ('draft', 'active', 'superseded')", name="status_allowed"),
        CheckConstraint("review_after_days BETWEEN 1 AND 36500", name="review_after_days_range"),
        CheckConstraint(
            "archive_after_days IS NULL OR archive_after_days BETWEEN review_after_days AND 36500",
            name="archive_after_days_range",
        ),
        CheckConstraint("effective_until IS NULL OR effective_until > effective_from", name="effective_order"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "id"),
        Index("ix_retention_policies_organization_resource_status", "organization_id", "resource_type", "status"),
        Index(
            "uq_retention_policies_one_active",
            "organization_id",
            "resource_type",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    resource_type: Mapped[str] = mapped_column(String(32))
    policy_code: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'draft'"))
    review_after_days: Mapped[int] = mapped_column(Integer)
    archive_after_days: Mapped[int | None] = mapped_column(Integer)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class RetentionHoldModel(Base):
    __tablename__ = "retention_holds"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('prospect', 'contact', 'contact_channel', 'acquisition_record', "
            "'provenance_record', 'import_declaration')",
            name="resource_type_allowed",
        ),
        CheckConstraint(
            "reason_code IN ('legal_request', 'contractual_obligation', 'investigation', "
            "'data_subject_request', 'quality_review', 'other')",
            name="reason_code_allowed",
        ),
        CheckConstraint(
            "release_reason_code IS NULL OR release_reason_code IN ('resolved', 'expired', "
            "'entered_in_error', 'other')",
            name="release_reason_code_allowed",
        ),
        CheckConstraint("reason_code <> 'other' OR note IS NOT NULL", name="other_note"),
        CheckConstraint("released_at IS NULL OR released_at >= placed_at", name="release_order"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "id"),
        Index("ix_retention_holds_organization_resource", "organization_id", "resource_type", "resource_id"),
        Index(
            "ix_retention_holds_active",
            "organization_id",
            "resource_type",
            "resource_id",
            postgresql_where=text("released_at IS NULL"),
        ),
        Index(
            "uq_retention_holds_idempotency",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[UUID] = mapped_column()
    reason_code: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(500))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    placed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    release_reason_code: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    command_fingerprint: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class ImportDeclarationModel(Base):
    __tablename__ = "import_declarations"
    __table_args__ = (
        CheckConstraint("char_length(declaration_label) BETWEEN 1 AND 160", name="declaration_label_length"),
        CheckConstraint("format_code = 'csv'", name="format_code_allowed"),
        CheckConstraint("schema_code = 'prospect_contacts_v1'", name="schema_code_allowed"),
        CheckConstraint("jsonb_typeof(declared_field_codes) = 'array'", name="declared_field_codes_array"),
        CheckConstraint("jsonb_typeof(declared_data_categories) = 'array'", name="declared_data_categories_array"),
        CheckConstraint(
            "estimated_row_count IS NULL OR estimated_row_count BETWEEN 1 AND 10000000",
            name="estimated_row_count_range",
        ),
        CheckConstraint(
            "declared_content_sha256 IS NULL OR declared_content_sha256 ~ '^[a-f0-9]{64}$'",
            name="declared_content_sha256_format",
        ),
        CheckConstraint("status IN ('declared', 'quarantined', 'cancelled', 'archived')", name="status_allowed"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "acquisition_record_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_import_declarations_organization_status", "organization_id", "status"),
        Index("ix_import_declarations_organization_acquisition", "organization_id", "acquisition_record_id"),
        Index(
            "uq_import_declarations_idempotency",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    acquisition_record_id: Mapped[UUID] = mapped_column()
    declaration_label: Mapped[str] = mapped_column(String(160))
    format_code: Mapped[str] = mapped_column(String(16))
    schema_code: Mapped[str] = mapped_column(String(64))
    declared_field_codes: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    declared_data_categories: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    estimated_row_count: Mapped[int | None] = mapped_column(Integer)
    declared_content_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    decision_reason_codes: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    declared_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    archive_reason_code: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    command_fingerprint: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class CsvImportSessionModel(Base):
    __tablename__ = "csv_import_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "declaration_id"],
            ["import_declarations.organization_id", "import_declarations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_csv_import_sessions_organization_id_id"),
        Index("ix_csv_import_sessions_organization_declaration", "organization_id", "declaration_id"),
        Index("ix_csv_import_sessions_expiry", "expires_at"),
        CheckConstraint("content_sha256 ~ '^[a-f0-9]{64}$'", name="sha256"),
        CheckConstraint("byte_size BETWEEN 1 AND 10485760", name="size"),
        CheckConstraint(
            "jsonb_typeof(headers) = 'array' AND jsonb_array_length(headers) BETWEEN 1 AND 50",
            name="headers",
        ),
        CheckConstraint("jsonb_typeof(mapping) = 'object'", name="mapping"),
        CheckConstraint(
            "status IN ('uploaded', 'mapped', 'validated', 'confirmed', 'expired')",
            name="status",
        ),
        CheckConstraint("version > 0", name="version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    declaration_id: Mapped[UUID] = mapped_column()
    file_ref: Mapped[str] = mapped_column(String(64))
    content_sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    headers: Mapped[list[str]] = mapped_column(JSONB)
    mapping: Mapped[dict[str, str]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    row_count: Mapped[int | None] = mapped_column(Integer)
    ready_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    duplicate_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    review_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    quarantined_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class CsvImportRunModel(Base):
    __tablename__ = "csv_import_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "session_id"],
            ["csv_import_sessions.organization_id", "csv_import_sessions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_csv_import_runs_organization_id_id"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_csv_import_runs_idempotency"),
        Index("ix_csv_import_runs_organization_session", "organization_id", "session_id"),
        CheckConstraint("command_fingerprint ~ '^[a-f0-9]{64}$'", name="fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    session_id: Mapped[UUID] = mapped_column()
    idempotency_key: Mapped[str] = mapped_column(String(128))
    command_fingerprint: Mapped[str] = mapped_column(String(128))
    created_count: Mapped[int] = mapped_column(Integer)
    duplicate_count: Mapped[int] = mapped_column(Integer)
    review_count: Mapped[int] = mapped_column(Integer)
    quarantined_count: Mapped[int] = mapped_column(Integer)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CsvImportQuarantineModel(Base):
    __tablename__ = "csv_import_quarantines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "run_id"],
            ["csv_import_runs.organization_id", "csv_import_runs.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "run_id", "line_number", name="uq_csv_import_quarantines_line"),
        CheckConstraint("line_number > 1", name="line"),
        CheckConstraint("jsonb_typeof(reason_codes) = 'array'", name="reasons"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    run_id: Mapped[UUID] = mapped_column()
    line_number: Mapped[int] = mapped_column(Integer)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB)
    opaque_reference: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CsvImportFingerprintModel(Base):
    __tablename__ = "csv_import_fingerprints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"],
            ["prospects.organization_id", "prospects.id"],
            ondelete="CASCADE",
        ),
        PrimaryKeyConstraint("organization_id", "fingerprint"),
        CheckConstraint("fingerprint ~ '^[a-f0-9]{64}$'", name="fingerprint"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    prospect_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
