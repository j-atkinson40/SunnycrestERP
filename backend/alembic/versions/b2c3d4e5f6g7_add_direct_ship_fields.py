"""Add direct ship fields to deliveries and is_direct_ship_product to products.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Products: is_direct_ship_product ---
    op.add_column(
        "products",
        sa.Column("is_direct_ship_product", sa.Boolean(), nullable=True, server_default="false"),
    )

    # --- Deliveries: direct ship fields ---
    op.add_column(
        "deliveries",
        sa.Column("direct_ship_status", sa.String(30), nullable=True),
    )
    op.add_column(
        "deliveries",
        sa.Column("wilbert_order_number", sa.String(100), nullable=True),
    )
    op.add_column(
        "deliveries",
        sa.Column("direct_ship_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "deliveries",
        sa.Column("marked_shipped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deliveries",
        sa.Column("marked_shipped_by", sa.String(36), nullable=True),
    )

    op.create_index(
        "ix_deliveries_direct_ship_status",
        "deliveries",
        ["direct_ship_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_deliveries_direct_ship_status", table_name="deliveries")
    op.drop_column("deliveries", "marked_shipped_by")
    op.drop_column("deliveries", "marked_shipped_at")
    op.drop_column("deliveries", "direct_ship_notes")
    op.drop_column("deliveries", "wilbert_order_number")
    op.drop_column("deliveries", "direct_ship_status")
    op.drop_column("products", "is_direct_ship_product")
