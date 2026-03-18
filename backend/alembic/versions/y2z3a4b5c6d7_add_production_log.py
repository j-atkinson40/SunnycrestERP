"""Add production log tables.

Revision ID: y2z3a4b5c6d7
Revises: x1y2z3a4b5c6
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa

revision = "y2z3a4b5c6d7"
down_revision = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- production_log_entries --
    op.create_table(
        "production_log_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("log_date", sa.Date, nullable=False, index=True),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity_produced", sa.Integer, nullable=False),
        sa.Column("mix_design_id", sa.String(36), nullable=True),
        sa.Column("mix_design_name", sa.String(255), nullable=True),
        sa.Column("batch_count", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "entered_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "entry_method",
            sa.String(20),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- production_log_summaries --
    op.create_table(
        "production_log_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("summary_date", sa.Date, nullable=False),
        sa.Column("total_units_produced", sa.Integer, server_default="0"),
        sa.Column("products_produced", sa.Text, nullable=True),
        sa.Column("recalculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "summary_date", name="uq_prod_log_summary_tenant_date"),
    )

    # -- Add group column to extension_definitions --
    op.add_column(
        "extension_definitions",
        sa.Column("group", sa.String(60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extension_definitions", "group")
    op.drop_table("production_log_summaries")
    op.drop_table("production_log_entries")
