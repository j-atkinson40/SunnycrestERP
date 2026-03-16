"""Add module definitions and vertical presets.

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "e4f5g6h7i8j9"
down_revision = "d3e4f5g6h7i8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "module_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(80), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("is_core", sa.Boolean, default=False),
        sa.Column("dependencies", sa.Text, nullable=True),
        sa.Column("feature_flags", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "vertical_presets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "preset_modules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("preset_id", sa.String(36), sa.ForeignKey("vertical_presets.id"), nullable=False),
        sa.Column("module_key", sa.String(80), nullable=False),
        sa.UniqueConstraint("preset_id", "module_key", name="uq_preset_module"),
    )

    op.create_table(
        "tenant_module_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("module_key", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "module_key", name="uq_tenant_module_config"),
    )

    op.add_column("companies", sa.Column("vertical", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_table("tenant_module_configs")
    op.drop_table("preset_modules")
    op.drop_table("vertical_presets")
    op.drop_table("module_definitions")
    op.drop_column("companies", "vertical")
