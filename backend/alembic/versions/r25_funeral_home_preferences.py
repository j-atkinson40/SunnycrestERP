"""r25 — funeral home preferences: prefers_placer, confirmation method, product flags, auto-added line items

Revision ID: r25_funeral_home_preferences
Revises: r24_historical_order_import
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r25_funeral_home_preferences"
down_revision = "r24_historical_order_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── customers ────────────────────────────────────────────────────────────
    # prefers_placer: auto-add vault placer on lowering device orders
    op.add_column(
        "customers",
        sa.Column("prefers_placer", sa.Boolean(), nullable=False, server_default="false"),
    )
    # preferred_confirmation_method: 'phone', 'email', 'text', 'any', or null
    op.add_column(
        "customers",
        sa.Column("preferred_confirmation_method", sa.String(20), nullable=True),
    )

    # ── products ─────────────────────────────────────────────────────────────
    # is_placer: identifies the Vault Placer product (safe to rename product)
    op.add_column(
        "products",
        sa.Column("is_placer", sa.Boolean(), nullable=False, server_default="false"),
    )
    # is_lowering_device: products that include a lowering device service
    op.add_column(
        "products",
        sa.Column("is_lowering_device", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ── sales_order_lines ────────────────────────────────────────────────────
    op.add_column(
        "sales_order_lines",
        sa.Column("is_auto_added", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "sales_order_lines",
        sa.Column("auto_add_reason", sa.String(50), nullable=True),
    )

    # ── quote_lines ──────────────────────────────────────────────────────────
    op.add_column(
        "quote_lines",
        sa.Column("is_auto_added", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "quote_lines",
        sa.Column("auto_add_reason", sa.String(50), nullable=True),
    )

    # ── sales_orders ─────────────────────────────────────────────────────────
    # confirmation_method: per-order override for preferred_confirmation_method
    op.add_column(
        "sales_orders",
        sa.Column("confirmation_method", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_orders", "confirmation_method")
    op.drop_column("quote_lines", "auto_add_reason")
    op.drop_column("quote_lines", "is_auto_added")
    op.drop_column("sales_order_lines", "auto_add_reason")
    op.drop_column("sales_order_lines", "is_auto_added")
    op.drop_column("products", "is_lowering_device")
    op.drop_column("products", "is_placer")
    op.drop_column("customers", "preferred_confirmation_method")
    op.drop_column("customers", "prefers_placer")
