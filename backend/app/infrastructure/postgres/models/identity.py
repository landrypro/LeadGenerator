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


class OrganizationModel(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 160", name="name_length"),
        CheckConstraint("status IN ('provisioning', 'active', 'suspended')", name="status_allowed"),
        CheckConstraint(
            "(status = 'provisioning' AND activated_at IS NULL) OR "
            "(status IN ('active', 'suspended') AND activated_at IS NOT NULL)",
            name="activation_state_consistent",
        ),
        CheckConstraint(
            "(creation_request_id IS NULL) = (creation_request_fingerprint IS NULL)",
            name="creation_idempotency_consistent",
        ),
        CheckConstraint(
            "creation_request_fingerprint IS NULL OR char_length(creation_request_fingerprint) = 64",
            name="creation_request_fingerprint_length",
        ),
        UniqueConstraint("creation_request_id"),
        CheckConstraint("google_search_daily_limit > 0", name="google_search_daily_limit_positive"),
        CheckConstraint("version > 0", name="version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    locale: Mapped[str] = mapped_column(String(16), server_default=text("'fr-CA'"))
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'provisioning'"))
    google_search_daily_limit: Mapped[int] = mapped_column(Integer, server_default=text("100"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT", use_alter=True))
    creation_request_id: Mapped[UUID | None] = mapped_column()
    creation_request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class OrganizationStatusOperationModel(Base):
    __tablename__ = "organization_status_operations"
    __table_args__ = (
        CheckConstraint("operation IN ('suspend', 'reactivate')", name="operation_allowed"),
        CheckConstraint("char_length(fingerprint) = 64", name="fingerprint_length"),
        CheckConstraint(
            "reason_code IN ('customer_request', 'billing', 'security', 'compliance', 'administrative', 'other')",
            name="reason_code_allowed",
        ),
        CheckConstraint(
            "external_reference IS NULL OR char_length(external_reference) BETWEEN 1 AND 64",
            name="external_reference_length",
        ),
        CheckConstraint("result_version > 0", name="result_version_positive"),
        Index("ix_organization_status_operations_organization_created", "organization_id", "created_at"),
    )

    operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    operation: Mapped[str] = mapped_column(String(16))
    fingerprint: Mapped[str] = mapped_column(String(64))
    reason_code: Mapped[str] = mapped_column(String(32))
    external_reference: Mapped[str | None] = mapped_column(String(64))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    result_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("char_length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("char_length(email_normalized) BETWEEN 3 AND 254", name="email_normalized_length"),
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 120", name="display_name_length"),
        CheckConstraint("status IN ('pending', 'active', 'disabled')", name="status_allowed"),
        CheckConstraint("platform_role IS NULL OR platform_role = 'platform_admin'", name="platform_role_allowed"),
        CheckConstraint("status = 'pending' OR password_hash IS NOT NULL", name="active_user_has_password"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("email_normalized"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254))
    email_normalized: Mapped[str] = mapped_column(String(254))
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    platform_role: Mapped[str | None] = mapped_column(String(32))
    last_active_organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class MembershipModel(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'manager', 'sales')", name="role_allowed"),
        CheckConstraint("status IN ('active', 'disabled')", name="status_allowed"),
        CheckConstraint("version > 0", name="version_positive"),
        UniqueConstraint("organization_id", "user_id"),
        UniqueConstraint("organization_id", "id"),
        Index("ix_memberships_user_id_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'active'"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class UserInvitationModel(Base):
    __tablename__ = "user_invitations"
    __table_args__ = (
        CheckConstraint("char_length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("char_length(email_normalized) BETWEEN 3 AND 254", name="email_normalized_length"),
        CheckConstraint("role IN ('admin', 'manager', 'sales')", name="role_allowed"),
        CheckConstraint(
            "invitation_kind IN ('initial_administrator', 'member')",
            name="invitation_kind_allowed",
        ),
        CheckConstraint("delivery_status IN ('pending', 'sent', 'failed')", name="delivery_status_allowed"),
        CheckConstraint("char_length(token_hash) = 64", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint("NOT (accepted_at IS NOT NULL AND revoked_at IS NOT NULL)", name="terminal_state_exclusive"),
        ForeignKeyConstraint(
            ["organization_id", "supersedes_invitation_id"],
            ["user_invitations.organization_id", "user_invitations.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "uq_user_invitations_active_organization_email",
            "organization_id",
            "email_normalized",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
        UniqueConstraint("token_hash"),
        UniqueConstraint("organization_id", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(254))
    email_normalized: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(16))
    invitation_kind: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    accepted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    supersedes_invitation_id: Mapped[UUID | None] = mapped_column()
    delivery_status: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    delivery_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class InvitationDeliveryAttemptModel(Base):
    __tablename__ = "invitation_delivery_attempts"
    __table_args__ = (
        CheckConstraint("kind IN ('initial', 'resend')", name="kind_allowed"),
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="status_allowed"),
        CheckConstraint(
            "failure_code IS NULL OR char_length(failure_code) BETWEEN 1 AND 64",
            name="failure_code_length",
        ),
        CheckConstraint(
            "(status = 'pending' AND completed_at IS NULL) OR (status <> 'pending' AND completed_at IS NOT NULL)",
            name="completion_consistent",
        ),
        ForeignKeyConstraint(
            ["organization_id", "invitation_id"],
            ["user_invitations.organization_id", "user_invitations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("request_id"),
        UniqueConstraint("invitation_id"),
        Index("ix_invitation_delivery_attempts_org_kind_created", "organization_id", "kind", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    invitation_id: Mapped[UUID] = mapped_column()
    request_id: Mapped[UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'pending'"))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
