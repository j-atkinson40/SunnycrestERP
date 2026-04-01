"""Add service location, service time, and ETA fields to sales_orders.

Revision ID: r34_order_service_fields
Revises: r33_lifecycle_gaps
"""

from alembic import op
import sqlalchemy as sa

revision = "r34_order_service_fields"
down_revision = "r33_lifecycle_gaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_orders",
        sa.Column("service_location", sa.String(20), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("service_location_other", sa.String(100), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("service_time", sa.Time, nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("eta", sa.Time, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_orders", "eta")
    op.drop_column("sales_orders", "service_time")
    op.drop_column("sales_orders", "service_location_other")
    op.drop_column("sales_orders", "service_location")
