"""Add require_driver_status_updates to delivery_settings and delivery
confirmation tracking columns to sales_orders.

Revision ID: r13_driver_status_updates
Revises: r12_catalog_safety_net
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r13_driver_status_updates"
down_revision = "r12_catalog_safety_net"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.add_column is monkey-patched in env.py to be idempotent (skips if column exists)

    # delivery_settings — driver confirmation mode
    op.add_column(
        "delivery_settings",
        sa.Column("require_driver_status_updates", sa.Boolean(), nullable=False, server_default="false"),
    )

    # sales_orders — delivery confirmation tracking
    op.add_column(
        "sales_orders",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("delivery_auto_confirmed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "sales_orders",
        sa.Column("delivered_by_driver_name", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_orders", "delivered_by_driver_name")
    op.drop_column("sales_orders", "delivery_auto_confirmed")
    op.drop_column("sales_orders", "delivered_at")
    op.drop_column("delivery_settings", "require_driver_status_updates")
