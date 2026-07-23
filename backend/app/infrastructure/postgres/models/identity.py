from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 160", name="name_length"),
        CheckConstraint("status IN ('active', 'suspended')", name="status_allowed"),
        CheckConstraint("google_search_daily_limit > 0", name="google_search_daily_limit_positive"),
        CheckConstraint("version > 0", name="version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    locale: Mapped[str] = mapped_column(String(16), server_default=text("'fr-CA'"))
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'active'"))
    google_search_daily_limit: Mapped[int] = mapped_column(Integer, server_default=text("100"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


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
        UniqueConstraint("organization_id", "user_id"),
        Index("ix_memberships_user_id_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), server_default=text("'active'"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class UserInvitationModel(Base):
    __tablename__ = "user_invitations"
    __table_args__ = (
        CheckConstraint("char_length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("char_length(email_normalized) BETWEEN 3 AND 254", name="email_normalized_length"),
        CheckConstraint("role IN ('admin', 'manager', 'sales')", name="role_allowed"),
        CheckConstraint("char_length(token_hash) = 64", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        Index(
            "uq_user_invitations_active_organization_email",
            "organization_id",
            "email_normalized",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
        UniqueConstraint("token_hash"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(254))
    email_normalized: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
