"""Add ancillary order fields to deliveries table.

Revision ID: a1b2c3d4e5f6
Revises: z5a6b7c8d9e0
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "z5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # scheduling_type: 'kanban' | 'ancillary' — NULL means kanban (legacy orders)
    op.add_column(
        "deliveries",
        sa.Column("scheduling_type", sa.String(20), nullable=True),
    )
    # ancillary_fulfillment_status: tracks ancillary order lifecycle
    op.add_column(
        "deliveries",
        sa.Column("ancillary_fulfillment_status", sa.String(30), nullable=True),
    )
    # assigned_driver_id: driver assigned to an ancillary order (not via route/stop)
    op.add_column(
        "deliveries",
        sa.Column("assigned_driver_id", sa.String(36), nullable=True),
    )
    # pickup fields
    op.add_column(
        "deliveries",
        sa.Column("pickup_expected_by", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deliveries",
        sa.Column("pickup_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deliveries",
        sa.Column("pickup_confirmed_by", sa.String(200), nullable=True),
    )

    # Index for fast ancillary queries
    op.create_index(
        "ix_deliveries_scheduling_type",
        "deliveries",
        ["scheduling_type"],
    )
    op.create_index(
        "ix_deliveries_ancillary_status",
        "deliveries",
        ["ancillary_fulfillment_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_deliveries_ancillary_status", table_name="deliveries")
    op.drop_index("ix_deliveries_scheduling_type", table_name="deliveries")
    op.drop_column("deliveries", "pickup_confirmed_by")
    op.drop_column("deliveries", "pickup_confirmed_at")
    op.drop_column("deliveries", "pickup_expected_by")
    op.drop_column("deliveries", "assigned_driver_id")
    op.drop_column("deliveries", "ancillary_fulfillment_status")
    op.drop_column("deliveries", "scheduling_type")
