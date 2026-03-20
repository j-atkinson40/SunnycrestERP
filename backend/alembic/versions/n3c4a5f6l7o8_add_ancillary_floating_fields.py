"""Add ancillary floating fields to deliveries.

Revision ID: n3c4a5f6l7o8
Revises: n2b3d4s5h6i7
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa

revision = "n3c4a5f6l7o8"
down_revision = "n2b3d4s5h6i7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deliveries",
        sa.Column("ancillary_is_floating", sa.Boolean(), nullable=True, server_default="false"),
    )
    op.add_column(
        "deliveries",
        sa.Column("ancillary_soft_target_date", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_deliveries_ancillary_floating",
        "deliveries",
        ["ancillary_is_floating"],
    )


def downgrade() -> None:
    op.drop_index("ix_deliveries_ancillary_floating", table_name="deliveries")
    op.drop_column("deliveries", "ancillary_soft_target_date")
    op.drop_column("deliveries", "ancillary_is_floating")
