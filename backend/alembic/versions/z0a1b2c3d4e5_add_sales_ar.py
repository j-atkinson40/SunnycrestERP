"""add sales AR: quotes, sales_orders, invoices, customer_payments

Revision ID: z0a1b2c3d4e5
Revises: y9z0a1b2c3d4
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

revision = "z0a1b2c3d4e5"
down_revision = "y9z0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Quotes ---
    op.create_table(
        "quotes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("quote_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_terms", sa.String(50), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_rate", sa.Numeric(5, 4), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("converted_to_order_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "quote_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("quotes.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    # --- Sales Orders ---
    op.create_table(
        "sales_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("quotes.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_terms", sa.String(50), nullable=True),
        sa.Column("ship_to_name", sa.String(200), nullable=True),
        sa.Column("ship_to_address", sa.String(500), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_rate", sa.Numeric(5, 4), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "sales_order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sales_order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("quantity_shipped", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    # --- Invoices ---
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("sales_order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_terms", sa.String(50), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_rate", sa.Numeric(5, 4), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sage_invoice_id", sa.String(100), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    # --- Customer Payments ---
    op.create_table(
        "customer_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False, server_default="check"),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sage_payment_id", sa.String(100), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "customer_payment_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("customer_payments.id"), nullable=False, index=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("amount_applied", sa.Numeric(12, 2), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("customer_payment_applications")
    op.drop_table("customer_payments")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("sales_order_lines")
    op.drop_table("sales_orders")
    op.drop_table("quote_lines")
    op.drop_table("quotes")
