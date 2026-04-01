"""Add lifecycle tracking columns to sales_orders.

Revision ID: r33_lifecycle_gaps
Revises: r32_production_mold_config
"""

from alembic import op
import sqlalchemy as sa

revision = "r33_lifecycle_gaps"
down_revision = "r32_production_mold_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_orders",
        sa.Column("driver_confirmed", sa.Boolean, server_default="false"),
    )
    op.add_column(
        "sales_orders",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("has_inventory_warning", sa.Boolean, server_default="false"),
    )
    op.add_column(
        "sales_orders",
        sa.Column("inventory_warning_notes", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_orders", "inventory_warning_notes")
    op.drop_column("sales_orders", "has_inventory_warning")
    op.drop_column("sales_orders", "completed_at")
    op.drop_column("sales_orders", "driver_confirmed")
