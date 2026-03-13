"""Add AP & Purchasing tables (purchase_orders, vendor_bills, vendor_payments)

Revision ID: s3m4n5o6p7q8
Revises: r2l3m4n5o6p7
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "s3m4n5o6p7q8"
down_revision = "r2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # purchase_orders
    # -----------------------------------------------------------------------
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "order_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expected_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipping_address", sa.Text, nullable=True),
        sa.Column(
            "subtotal",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "tax_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "modified_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("number", "company_id", name="uq_po_number_company"),
    )

    # -----------------------------------------------------------------------
    # purchase_order_lines
    # -----------------------------------------------------------------------
    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "po_id",
            sa.String(36),
            sa.ForeignKey("purchase_orders.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=True,
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(10, 3), nullable=False),
        sa.Column(
            "quantity_received",
            sa.Numeric(10, 3),
            nullable=False,
            server_default="0",
        ),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "sort_order", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -----------------------------------------------------------------------
    # vendor_bills
    # -----------------------------------------------------------------------
    op.create_table(
        "vendor_bills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("vendor_invoice_number", sa.String(100), nullable=True),
        sa.Column(
            "po_id",
            sa.String(36),
            sa.ForeignKey("purchase_orders.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("bill_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "subtotal",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "tax_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "amount_paid",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("payment_terms", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "approved_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "modified_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -----------------------------------------------------------------------
    # vendor_bill_lines
    # -----------------------------------------------------------------------
    op.create_table(
        "vendor_bill_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "bill_id",
            sa.String(36),
            sa.ForeignKey("vendor_bills.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "po_line_id",
            sa.String(36),
            sa.ForeignKey("purchase_order_lines.id"),
            nullable=True,
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("expense_category", sa.String(100), nullable=True),
        sa.Column(
            "sort_order", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -----------------------------------------------------------------------
    # vendor_payments
    # -----------------------------------------------------------------------
    op.create_table(
        "vendor_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "modified_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -----------------------------------------------------------------------
    # vendor_payment_applications
    # -----------------------------------------------------------------------
    op.create_table(
        "vendor_payment_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "payment_id",
            sa.String(36),
            sa.ForeignKey("vendor_payments.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "bill_id",
            sa.String(36),
            sa.ForeignKey("vendor_bills.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("amount_applied", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("vendor_payment_applications")
    op.drop_table("vendor_payments")
    op.drop_table("vendor_bill_lines")
    op.drop_table("vendor_bills")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
