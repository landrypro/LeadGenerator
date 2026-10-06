"""Schéma isolé de la Pré-Phase 5 Automatisation.

Les modèles ne sont pas encore reliés à une route, un worker ou un cas d'usage.
Ils décrivent seulement le socle `P4-Lite`, fermé par défaut et séparé des
objets CRM canoniques.
"""

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
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from .base import Base


class AutomationOrganizationSettingsModel(Base):
    __tablename__ = "automation_organization_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_automation_settings_organization"),
        CheckConstraint("suspension_generation >= 0", name="ck_automation_settings_suspension_generation"),
        CheckConstraint("version > 0", name="ck_automation_settings_version"),
        Index("ix_automation_settings_org_enabled", "organization_id", "automation_enabled"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    automation_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    suspension_generation: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class AutomationPlaybookModel(Base):
    __tablename__ = "automation_playbooks"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_automation_playbooks_org_id"),
        UniqueConstraint("organization_id", "code", name="uq_automation_playbooks_org_code"),
        CheckConstraint(
            "code IN ('new_prospect','proposal_pending','forgotten_opportunity')",
            name="ck_automation_playbooks_code",
        ),
        CheckConstraint(
            "state IN ('draft','preflight_required','preflight_running','ready','active_prepare','suspended','retired')",
            name="ck_automation_playbooks_state",
        ),
        CheckConstraint("suspension_generation >= 0", name="ck_automation_playbooks_suspension_generation"),
        CheckConstraint("version > 0", name="ck_automation_playbooks_version"),
        Index("ix_automation_playbooks_org_state", "organization_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    code: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), server_default=text("'draft'"))
    prepare_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    suspension_generation: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class AutomationPlaybookVersionModel(Base):
    __tablename__ = "automation_playbook_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_automation_playbook_versions_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "playbook_id"],
            ["automation_playbooks.organization_id", "automation_playbooks.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_number > 0", name="ck_automation_playbook_versions_number"),
        CheckConstraint("snapshot_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_playbook_versions_fingerprint"),
        CheckConstraint("jsonb_typeof(configuration) = 'object'", name="ck_automation_playbook_versions_config"),
        Index(
            "uq_automation_playbook_versions_org_playbook_number",
            "organization_id",
            "playbook_id",
            "version_number",
            unique=True,
        ),
        Index("ix_automation_playbook_versions_org_created", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    playbook_id: Mapped[UUID] = mapped_column()
    version_number: Mapped[int] = mapped_column(Integer)
    ruleset_version: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    snapshot_fingerprint: Mapped[str] = mapped_column(String(64))
    created_by_membership_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AutomationPreflightModel(Base):
    __tablename__ = "automation_preflights"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_automation_preflights_org_id"),
        UniqueConstraint("organization_id", "correlation_id", name="uq_automation_preflights_org_correlation"),
        ForeignKeyConstraint(
            ["organization_id", "playbook_version_id"],
            ["automation_playbook_versions.organization_id", "automation_playbook_versions.id"],
            name="fk_automation_preflights_org_playbook_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "requested_by_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_automation_preflights_org_requester",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "state IN ('queued','running','completed','needs_review','failed','stale','cancelled')",
            name="ck_automation_preflights_state",
        ),
        CheckConstraint("scope_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_preflights_scope_fingerprint"),
        CheckConstraint("subject_count >= 0", name="ck_automation_preflights_subject_count"),
        CheckConstraint("green_count >= 0", name="ck_automation_preflights_green_count"),
        CheckConstraint("yellow_count >= 0", name="ck_automation_preflights_yellow_count"),
        CheckConstraint("red_count >= 0", name="ck_automation_preflights_red_count"),
        CheckConstraint("to_verify_count >= 0", name="ck_automation_preflights_to_verify_count"),
        CheckConstraint("expires_at > created_at", name="ck_automation_preflights_expiry"),
        Index("ix_automation_preflights_org_state_created", "organization_id", "state", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    playbook_version_id: Mapped[UUID] = mapped_column()
    requested_by_membership_id: Mapped[UUID] = mapped_column()
    ruleset_version: Mapped[str] = mapped_column(String(64))
    scope_fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), server_default=text("'queued'"))
    correlation_id: Mapped[UUID] = mapped_column()
    subject_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    green_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    yellow_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    red_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    to_verify_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AutomationDecisionModel(Base):
    __tablename__ = "automation_decisions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_automation_decisions_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "playbook_version_id"],
            ["automation_playbook_versions.organization_id", "automation_playbook_versions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "preflight_id"],
            ["automation_preflights.organization_id", "automation_preflights.id"],
            name="fk_automation_decisions_org_preflight",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "preflight_id",
            "subject_type",
            "subject_id",
            name="uq_automation_decisions_org_preflight_subject",
        ),
        CheckConstraint("subject_type IN ('prospect','opportunity')", name="ck_automation_decisions_subject_type"),
        CheckConstraint(
            "fire_level IN ('red','yellow','green','to_verify')", name="ck_automation_decisions_fire_level"
        ),
        CheckConstraint("next_action IN ('refuse','verify','prepare')", name="ck_automation_decisions_next_action"),
        CheckConstraint(
            "outcome IN ('prepared','refused','stale','to_verify')", name="ck_automation_decisions_outcome"
        ),
        CheckConstraint("context_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_decisions_context_fingerprint"),
        CheckConstraint("jsonb_typeof(reason_codes) = 'array'", name="ck_automation_decisions_reason_codes"),
        CheckConstraint("expires_at > created_at", name="ck_automation_decisions_expiry"),
        Index("ix_automation_decisions_org_preflight", "organization_id", "preflight_id", "created_at"),
        Index("ix_automation_decisions_org_subject", "organization_id", "subject_type", "subject_id", "created_at"),
        Index("uq_automation_decisions_org_correlation", "organization_id", "correlation_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    preflight_id: Mapped[UUID] = mapped_column()
    playbook_version_id: Mapped[UUID] = mapped_column()
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[UUID] = mapped_column()
    fire_level: Mapped[str] = mapped_column(String(16))
    next_action: Mapped[str] = mapped_column(String(16))
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    context_fingerprint: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[UUID] = mapped_column()
    outcome: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AutomationAdmissionModel(Base):
    __tablename__ = "automation_admissions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_automation_admissions_org_id"),
        UniqueConstraint("organization_id", "idempotency_key_digest", name="uq_automation_admissions_org_idempotency"),
        UniqueConstraint(
            "organization_id",
            "prospect_id",
            "playbook_version_id",
            "functional_identity_fingerprint",
            name="uq_automation_admissions_functional_identity",
        ),
        ForeignKeyConstraint(
            ["organization_id", "prospect_id"],
            ["prospects.organization_id", "prospects.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "playbook_version_id"],
            ["automation_playbook_versions.organization_id", "automation_playbook_versions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "requested_by_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "preflight_id"],
            ["automation_preflights.organization_id", "automation_preflights.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decision_id"],
            ["automation_decisions.organization_id", "automation_decisions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "task_id"],
            ["prospect_tasks.organization_id", "prospect_tasks.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="RESTRICT"),
        CheckConstraint(
            "state IN ('accepted','preflight_required','ready_to_prepare','prepared','blocked','quarantined','to_verify','rejected','cancelled')",
            name="ck_automation_admissions_state",
        ),
        CheckConstraint(
            "functional_identity_fingerprint ~ '^[a-f0-9]{64}$'",
            name="ck_automation_admissions_functional_identity",
        ),
        CheckConstraint("idempotency_key_digest ~ '^[a-f0-9]{64}$'", name="ck_automation_admissions_idempotency"),
        CheckConstraint("request_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_admissions_request"),
        Index(
            "uq_automation_admissions_org_job",
            "organization_id",
            "job_id",
            unique=True,
            postgresql_where=text("job_id IS NOT NULL"),
        ),
        Index("ix_automation_admissions_org_state_created", "organization_id", "state", "created_at"),
        Index("ix_automation_admissions_org_prospect", "organization_id", "prospect_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    prospect_id: Mapped[UUID] = mapped_column()
    playbook_version_id: Mapped[UUID] = mapped_column()
    requested_by_membership_id: Mapped[UUID] = mapped_column()
    assigned_membership_id: Mapped[UUID | None] = mapped_column()
    preflight_id: Mapped[UUID] = mapped_column()
    decision_id: Mapped[UUID] = mapped_column()
    task_id: Mapped[UUID | None] = mapped_column()
    job_id: Mapped[UUID | None] = mapped_column()
    functional_identity_fingerprint: Mapped[str] = mapped_column(String(64))
    idempotency_key_digest: Mapped[str] = mapped_column(String(64))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[UUID] = mapped_column()
    state: Mapped[str] = mapped_column(String(32), server_default=text("'accepted'"))
    result_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationExceptionModel(Base):
    __tablename__ = "automation_exceptions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_automation_exceptions_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "decision_id"],
            ["automation_decisions.organization_id", "automation_decisions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("subject_type IN ('prospect','opportunity')", name="ck_automation_exceptions_subject_type"),
        CheckConstraint(
            "exception_code IN ('owner_unavailable','ambiguous_match','effect_uncertain','source_unavailable')",
            name="ck_automation_exceptions_code",
        ),
        CheckConstraint(
            "state IN ('open','in_progress','resolved','abandoned')", name="ck_automation_exceptions_state"
        ),
        CheckConstraint("version > 0", name="ck_automation_exceptions_version"),
        Index("ix_automation_exceptions_org_state", "organization_id", "state", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    decision_id: Mapped[UUID] = mapped_column()
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[UUID] = mapped_column()
    exception_code: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), server_default=text("'open'"))
    assigned_membership_id: Mapped[UUID | None] = mapped_column()
    resolution_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
