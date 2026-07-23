"""Créer les tables d’identité de l’incrément 2.2.

Revision ID: 20260723_0002
Revises: 20260722_0001
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0002"
down_revision: str | None = "20260722_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("locale", sa.String(length=16), server_default=sa.text("'fr-CA'"), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("google_search_daily_limit", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "google_search_daily_limit > 0",
            name=op.f("ck_organizations_google_search_daily_limit_positive"),
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 160", name=op.f("ck_organizations_name_length")),
        sa.CheckConstraint("status IN ('active', 'suspended')", name=op.f("ck_organizations_status_allowed")),
        sa.CheckConstraint("version > 0", name=op.f("ck_organizations_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("platform_role", sa.String(length=32), nullable=True),
        sa.Column("last_active_organization_id", sa.Uuid(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "status = 'pending' OR password_hash IS NOT NULL", name=op.f("ck_users_active_user_has_password")
        ),
        sa.CheckConstraint("char_length(display_name) BETWEEN 1 AND 120", name=op.f("ck_users_display_name_length")),
        sa.CheckConstraint("char_length(email) BETWEEN 3 AND 254", name=op.f("ck_users_email_length")),
        sa.CheckConstraint(
            "char_length(email_normalized) BETWEEN 3 AND 254",
            name=op.f("ck_users_email_normalized_length"),
        ),
        sa.CheckConstraint(
            "platform_role IS NULL OR platform_role = 'platform_admin'",
            name=op.f("ck_users_platform_role_allowed"),
        ),
        sa.CheckConstraint("status IN ('pending', 'active', 'disabled')", name=op.f("ck_users_status_allowed")),
        sa.CheckConstraint("version > 0", name=op.f("ck_users_version_positive")),
        sa.ForeignKeyConstraint(
            ["last_active_organization_id"],
            ["organizations.id"],
            name=op.f("fk_users_last_active_organization_id_organizations"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email_normalized", name=op.f("uq_users_email_normalized")),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("role IN ('admin', 'manager', 'sales')", name=op.f("ck_memberships_role_allowed")),
        sa.CheckConstraint("status IN ('active', 'disabled')", name=op.f("ck_memberships_status_allowed")),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_memberships_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_memberships_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("organization_id", "user_id", name=op.f("uq_memberships_organization_id_user_id")),
    )
    op.create_index("ix_memberships_user_id_status", "memberships", ["user_id", "status"], unique=False)

    op.create_table(
        "user_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(email_normalized) BETWEEN 3 AND 254",
            name=op.f("ck_user_invitations_email_normalized_length"),
        ),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254",
            name=op.f("ck_user_invitations_email_length"),
        ),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_user_invitations_expires_after_creation")),
        sa.CheckConstraint("role IN ('admin', 'manager', 'sales')", name=op.f("ck_user_invitations_role_allowed")),
        sa.CheckConstraint("char_length(token_hash) = 64", name=op.f("ck_user_invitations_token_hash_length")),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name=op.f("fk_user_invitations_invited_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_user_invitations_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_invitations_token_hash")),
    )
    op.create_index(
        "uq_user_invitations_active_organization_email",
        "user_invitations",
        ["organization_id", "email_normalized"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_invitations_active_organization_email", table_name="user_invitations")
    op.drop_table("user_invitations")
    op.drop_index("ix_memberships_user_id_status", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
