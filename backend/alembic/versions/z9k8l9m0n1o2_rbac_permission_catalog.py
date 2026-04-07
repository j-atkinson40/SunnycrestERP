"""Add permission_catalog, custom_permissions tables and extend user_permission_overrides.

Revision ID: z9k8l9m0n1o2
Revises: z9j7k8l9m0n1
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "z9k8l9m0n1o2"
down_revision = "z9j7k8l9m0n1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── permission_catalog ───────────────────────────────────────────────
    op.create_table(
        "permission_catalog",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(200), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="true"),
        sa.Column("is_toggle", sa.Boolean(), server_default="true"),
        sa.Column("default_for_roles", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── custom_permissions ───────────────────────────────────────────────
    op.create_table(
        "custom_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), server_default="'custom'"),
        sa.Column("notification_routing", sa.Boolean(), server_default="true"),
        sa.Column("access_gating", sa.Boolean(), server_default="false"),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_custom_perm_tenant_slug"),
    )

    # ── Extend user_permission_overrides ─────────────────────────────────
    op.add_column(
        "user_permission_overrides",
        sa.Column(
            "granted_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "user_permission_overrides",
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # Widen permission_key column to 200 chars (was 100)
    op.alter_column(
        "user_permission_overrides",
        "permission_key",
        type_=sa.String(200),
        existing_type=sa.String(100),
    )
    op.alter_column(
        "role_permissions",
        "permission_key",
        type_=sa.String(200),
        existing_type=sa.String(100),
    )


def downgrade() -> None:
    op.alter_column(
        "role_permissions",
        "permission_key",
        type_=sa.String(100),
        existing_type=sa.String(200),
    )
    op.alter_column(
        "user_permission_overrides",
        "permission_key",
        type_=sa.String(100),
        existing_type=sa.String(200),
    )
    op.drop_column("user_permission_overrides", "notes")
    op.drop_column("user_permission_overrides", "granted_by_user_id")
    op.drop_table("custom_permissions")
    op.drop_table("permission_catalog")
