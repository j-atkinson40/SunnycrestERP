"""Add invoice review fields, order_type/scheduled_date/driver_exceptions to sales_orders,
and invoice_generation_mode to delivery_settings.

Revision ID: r11_invoice_review_fields
Revises: r10_merge_all_heads
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r11_invoice_review_fields"
down_revision = "r10_merge_all_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # invoices — review workflow columns
    # ------------------------------------------------------------------
    op.add_column("invoices", sa.Column("requires_review", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("invoices", sa.Column("review_due_date", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("auto_generated", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("invoices", sa.Column("generation_reason", sa.String(50), nullable=True))
    op.add_column("invoices", sa.Column("has_exceptions", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("invoices", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("invoices", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("invoices", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    # ------------------------------------------------------------------
    # sales_orders — order classification + driver exception fields
    # ------------------------------------------------------------------
    op.add_column("sales_orders", sa.Column("order_type", sa.String(50), nullable=True))
    op.add_column("sales_orders", sa.Column("scheduled_date", sa.Date(), nullable=True))
    op.add_column("sales_orders", sa.Column("driver_exceptions", postgresql.JSONB(), nullable=True))
    op.add_column("sales_orders", sa.Column("has_driver_exception", sa.Boolean(), nullable=True, server_default="false"))

    # ------------------------------------------------------------------
    # delivery_settings — invoice generation mode
    # ------------------------------------------------------------------
    op.add_column(
        "delivery_settings",
        sa.Column("invoice_generation_mode", sa.String(20), nullable=True, server_default="end_of_day"),
    )


def downgrade() -> None:
    op.drop_column("delivery_settings", "invoice_generation_mode")

    op.drop_column("sales_orders", "has_driver_exception")
    op.drop_column("sales_orders", "driver_exceptions")
    op.drop_column("sales_orders", "scheduled_date")
    op.drop_column("sales_orders", "order_type")

    op.drop_column("invoices", "approved_at")
    op.drop_column("invoices", "approved_by")
    op.drop_column("invoices", "reviewed_at")
    op.drop_column("invoices", "reviewed_by")
    op.drop_column("invoices", "review_notes")
    op.drop_column("invoices", "has_exceptions")
    op.drop_column("invoices", "generation_reason")
    op.drop_column("invoices", "auto_generated")
    op.drop_column("invoices", "review_due_date")
    op.drop_column("invoices", "requires_review")
