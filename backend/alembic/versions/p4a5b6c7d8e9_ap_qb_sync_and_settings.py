"""Add QB sync fields to vendors/bills/payments + ap_settings table.

Revision ID: p4a5b6c7d8e9
Revises: p3a4b5c6d7e8
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op

revision = "p4a5b6c7d8e9"
down_revision = "p3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # QB sync fields on vendors
    op.add_column("vendors", sa.Column("quickbooks_vendor_id", sa.String(100), nullable=True))
    op.add_column("vendors", sa.Column("quickbooks_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vendors", sa.Column("quickbooks_sync_error", sa.Text(), nullable=True))
    op.add_column("vendors", sa.Column("is_1099_vendor", sa.Boolean(), server_default="false"))

    # QB sync fields on vendor_bills (qbo_id already exists)
    op.add_column("vendor_bills", sa.Column("quickbooks_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vendor_bills", sa.Column("quickbooks_sync_error", sa.Text(), nullable=True))
    # Received statement linkage
    op.add_column("vendor_bills", sa.Column("received_statement_id", sa.String(36), nullable=True))
    op.add_column("vendor_bills", sa.Column("source", sa.String(30), server_default="manual"))
    # Attachment
    op.add_column("vendor_bills", sa.Column("attachment_url", sa.String(500), nullable=True))
    op.add_column("vendor_bills", sa.Column("attachment_filename", sa.String(255), nullable=True))

    # QB sync fields on vendor_payments
    op.add_column("vendor_payments", sa.Column("quickbooks_payment_id", sa.String(100), nullable=True))
    op.add_column("vendor_payments", sa.Column("quickbooks_synced_at", sa.DateTime(timezone=True), nullable=True))

    # AP settings per tenant
    op.create_table(
        "ap_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("default_payment_terms", sa.String(50), server_default="Net 30"),
        sa.Column("default_expense_category", sa.String(100), nullable=True),
        sa.Column("bill_approval_required", sa.Boolean(), server_default="false"),
        sa.Column("bill_approval_threshold", sa.Numeric(10, 2), nullable=True),
        sa.Column("quickbooks_ap_account_id", sa.String(100), nullable=True),
        sa.Column("quickbooks_default_expense_account_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ap_settings")
    op.drop_column("vendor_payments", "quickbooks_synced_at")
    op.drop_column("vendor_payments", "quickbooks_payment_id")
    op.drop_column("vendor_bills", "attachment_filename")
    op.drop_column("vendor_bills", "attachment_url")
    op.drop_column("vendor_bills", "source")
    op.drop_column("vendor_bills", "received_statement_id")
    op.drop_column("vendor_bills", "quickbooks_sync_error")
    op.drop_column("vendor_bills", "quickbooks_synced_at")
    op.drop_column("vendors", "is_1099_vendor")
    op.drop_column("vendors", "quickbooks_sync_error")
    op.drop_column("vendors", "quickbooks_synced_at")
    op.drop_column("vendors", "quickbooks_vendor_id")
