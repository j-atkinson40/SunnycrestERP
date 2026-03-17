"""Add qbo_id fields for QuickBooks Online sync tracking.

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa

revision = "h7i8j9k0l1m2"
down_revision = "g6h7i8j9k0l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("qbo_id", sa.String(100), nullable=True))
    op.add_column("customer_payments", sa.Column("qbo_id", sa.String(100), nullable=True))
    op.add_column("vendor_bills", sa.Column("qbo_id", sa.String(100), nullable=True))
    op.add_column("vendor_payments", sa.Column("qbo_id", sa.String(100), nullable=True))

    # Index for quick lookup of already-synced records
    op.create_index("ix_invoices_qbo_id", "invoices", ["qbo_id"])
    op.create_index("ix_customer_payments_qbo_id", "customer_payments", ["qbo_id"])
    op.create_index("ix_vendor_bills_qbo_id", "vendor_bills", ["qbo_id"])
    op.create_index("ix_vendor_payments_qbo_id", "vendor_payments", ["qbo_id"])


def downgrade() -> None:
    op.drop_index("ix_vendor_payments_qbo_id", "vendor_payments")
    op.drop_index("ix_vendor_bills_qbo_id", "vendor_bills")
    op.drop_index("ix_customer_payments_qbo_id", "customer_payments")
    op.drop_index("ix_invoices_qbo_id", "invoices")

    op.drop_column("vendor_payments", "qbo_id")
    op.drop_column("vendor_bills", "qbo_id")
    op.drop_column("customer_payments", "qbo_id")
    op.drop_column("invoices", "qbo_id")
