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
    # Add approval/matching columns to existing purchase_orders table
    op.add_column("purchase_orders", sa.Column("requires_approval", sa.Boolean(), server_default="false"))
    op.add_column("purchase_orders", sa.Column("approval_status", sa.String(20), nullable=True))
    op.add_column("purchase_orders", sa.Column("submitted_for_approval_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchase_orders", sa.Column("submitted_by", sa.String(36), nullable=True))
    op.add_column("purchase_orders", sa.Column("approved_by", sa.String(36), nullable=True))
    op.add_column("purchase_orders", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchase_orders", sa.Column("rejected_by", sa.String(36), nullable=True))
    op.add_column("purchase_orders", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchase_orders", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("purchase_orders", sa.Column("expected_delivery_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("delivered_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("shipping_amount", sa.Numeric(12, 2), server_default="0"))
    op.add_column("purchase_orders", sa.Column("total_amount", sa.Numeric(12, 2), server_default="0"))
    op.add_column("purchase_orders", sa.Column("match_status", sa.String(20), server_default="pending_receipt"))
    op.add_column("purchase_orders", sa.Column("match_variance_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("purchase_orders", sa.Column("match_notes", sa.Text(), nullable=True))
    op.add_column("purchase_orders", sa.Column("internal_notes", sa.Text(), nullable=True))

    # Add quantity tracking to existing purchase_order_lines
    op.add_column("purchase_order_lines", sa.Column("quantity_received", sa.Numeric(12, 3), server_default="0"))
    op.add_column("purchase_order_lines", sa.Column("quantity_invoiced", sa.Numeric(12, 3), server_default="0"))
    op.add_column("purchase_order_lines", sa.Column("vendor_item_code", sa.String(100), nullable=True))
    op.add_column("purchase_order_lines", sa.Column("gl_account_id", sa.String(36), nullable=True))

    # PO receipts — new table
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

    # Link bills to POs
    op.add_column("bills", sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id"), nullable=True))
    op.add_column("bills", sa.Column("po_match_status", sa.String(20), server_default="no_po"))
    op.add_column("bills", sa.Column("po_match_variance", sa.Numeric(12, 2), nullable=True))
    op.add_column("bills", sa.Column("po_match_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bills", "po_match_notes")
    op.drop_column("bills", "po_match_variance")
    op.drop_column("bills", "po_match_status")
    op.drop_column("bills", "purchase_order_id")
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
