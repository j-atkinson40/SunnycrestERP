"""Add extension definitions and tenant extensions.

Revision ID: g6h7i8j9k0l1
Revises: f5g6h7i8j9k0
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "g6h7i8j9k0l1"
down_revision = "f5g6h7i8j9k0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extension_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("extension_key", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("module_key", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config_schema", sa.Text, nullable=True),
        sa.Column("version", sa.String(20), default="1.0.0"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tenant_extensions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("extension_key", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("config", sa.Text, nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "extension_key", name="uq_tenant_extension"),
    )


def downgrade() -> None:
    op.drop_table("tenant_extensions")
    op.drop_table("extension_definitions")
