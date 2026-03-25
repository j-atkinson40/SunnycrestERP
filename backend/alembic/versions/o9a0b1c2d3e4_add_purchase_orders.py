"""Add PO approval/matching fields, receipt tables, and bill-PO link.

Revision ID: o9a0b1c2d3e4
Revises: o8a9b0c1d2e3
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "o9a0b1c2d3e4"
down_revision = "o8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    def safe_add_columns(table_name, columns):
        """Add columns only if they don't already exist."""
        if table_name not in inspector.get_table_names():
            return
        existing = {c["name"] for c in inspector.get_columns(table_name)}
        for col_name, col_def in columns:
            if col_name not in existing:
                op.add_column(table_name, col_def)

    # Add approval/matching columns to purchase_orders (if they don't exist from creation)
    safe_add_columns("purchase_orders", [
        ("requires_approval", sa.Column("requires_approval", sa.Boolean(), server_default="false")),
        ("approval_status", sa.Column("approval_status", sa.String(20), nullable=True)),
        ("submitted_for_approval_at", sa.Column("submitted_for_approval_at", sa.DateTime(timezone=True), nullable=True)),
        ("submitted_by", sa.Column("submitted_by", sa.String(36), nullable=True)),
        ("approved_by", sa.Column("approved_by", sa.String(36), nullable=True)),
        ("approved_at", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)),
        ("rejected_by", sa.Column("rejected_by", sa.String(36), nullable=True)),
        ("rejected_at", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)),
        ("rejection_reason", sa.Column("rejection_reason", sa.Text(), nullable=True)),
        ("expected_delivery_date", sa.Column("expected_delivery_date", sa.Date(), nullable=True)),
        ("delivered_date", sa.Column("delivered_date", sa.Date(), nullable=True)),
        ("shipping_amount", sa.Column("shipping_amount", sa.Numeric(12, 2), server_default="0")),
        ("total_amount", sa.Column("total_amount", sa.Numeric(12, 2), server_default="0")),
        ("match_status", sa.Column("match_status", sa.String(20), server_default="pending_receipt")),
        ("match_variance_amount", sa.Column("match_variance_amount", sa.Numeric(12, 2), nullable=True)),
        ("match_notes", sa.Column("match_notes", sa.Text(), nullable=True)),
        ("internal_notes", sa.Column("internal_notes", sa.Text(), nullable=True)),
    ])

    # Add quantity tracking to purchase_order_lines
    safe_add_columns("purchase_order_lines", [
        ("quantity_received", sa.Column("quantity_received", sa.Numeric(12, 3), server_default="0")),
        ("quantity_invoiced", sa.Column("quantity_invoiced", sa.Numeric(12, 3), server_default="0")),
        ("vendor_item_code", sa.Column("vendor_item_code", sa.String(100), nullable=True)),
        ("gl_account_id", sa.Column("gl_account_id", sa.String(36), nullable=True)),
    ])

    # Link vendor_bills to POs
    safe_add_columns("vendor_bills", [
        ("purchase_order_id", sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id"), nullable=True)),
        ("po_match_status", sa.Column("po_match_status", sa.String(20), server_default="no_po")),
        ("po_match_variance", sa.Column("po_match_variance", sa.Numeric(12, 2), nullable=True)),
        ("po_match_notes", sa.Column("po_match_notes", sa.Text(), nullable=True)),
    ])

    table_names = inspector.get_table_names()

    # PO receipts — new table (skip if already exists)
    if "purchase_order_receipts" not in table_names:
        op.create_table(
            "purchase_order_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id"), nullable=False, index=True),
        sa.Column("receipt_number", sa.String(30), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("received_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="complete"),
        sa.Column("has_shortage", sa.Boolean(), server_default="false"),
        sa.Column("has_overage", sa.Boolean(), server_default="false"),
        sa.Column("has_damage", sa.Boolean(), server_default="false"),
        sa.Column("has_wrong_items", sa.Boolean(), server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # PO receipt lines — new table
    op.create_table(
        "purchase_order_receipt_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("receipt_id", sa.String(36), sa.ForeignKey("purchase_order_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("po_line_id", sa.String(36), sa.ForeignKey("purchase_order_lines.id"), nullable=True),
        sa.Column("quantity_received", sa.Numeric(12, 3), nullable=False),
        sa.Column("quantity_expected", sa.Numeric(12, 3), nullable=True),
        sa.Column("condition", sa.String(20), server_default="good"),
        sa.Column("condition_notes", sa.Text(), nullable=True),
        sa.Column("photo_paths", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # PO documents — new table
    op.create_table(
        "purchase_order_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_type", sa.String(30), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # vendor_bills PO link columns handled by safe_add_columns above


def downgrade() -> None:
    op.drop_column("vendor_bills", "po_match_notes")
    op.drop_column("vendor_bills", "po_match_variance")
    op.drop_column("vendor_bills", "po_match_status")
    op.drop_column("vendor_bills", "purchase_order_id")
    op.drop_table("purchase_order_documents")
    op.drop_table("purchase_order_receipt_lines")
    op.drop_table("purchase_order_receipts")
    for col in ["gl_account_id", "vendor_item_code", "quantity_invoiced", "quantity_received"]:
        op.drop_column("purchase_order_lines", col)
    for col in ["internal_notes", "match_notes", "match_variance_amount", "match_status",
                 "total_amount", "shipping_amount", "delivered_date", "expected_delivery_date",
                 "rejection_reason", "rejected_at", "rejected_by", "approved_at", "approved_by",
                 "submitted_by", "submitted_for_approval_at", "approval_status", "requires_approval"]:
        op.drop_column("purchase_orders", col)
