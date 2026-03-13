"""Add sage export config table

Revision ID: o9i0j1k2l3m4
Revises: n8h9i0j1k2l3
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "o9i0j1k2l3m4"
down_revision = "n8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sage_export_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("warehouse_code", sa.String(20), nullable=False, server_default="MAIN"),
        sa.Column("export_directory", sa.String(500), nullable=True),
        sa.Column("column_mapping", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_export_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("company_id", name="uq_sage_config_company"),
    )


def downgrade() -> None:
    op.drop_table("sage_export_configs")
