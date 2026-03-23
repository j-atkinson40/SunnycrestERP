"""Add cross-tenant statement delivery tables.

Revision ID: p2a3b4c5d6e7
Revises: p1a2b3c4d5e6
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op

revision = "p2a3b4c5d6e7"
down_revision = "p1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Received statements — funeral home side
    op.create_table(
        "received_statements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("from_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("from_tenant_name", sa.String(200), nullable=False),
        sa.Column("customer_statement_id", sa.String(36), nullable=False),
        sa.Column("statement_period_month", sa.Integer(), nullable=False),
        sa.Column("statement_period_year", sa.Integer(), nullable=False),
        sa.Column("previous_balance", sa.Numeric(12, 2), server_default="0"),
        sa.Column("new_charges", sa.Numeric(12, 2), server_default="0"),
        sa.Column("payments_received", sa.Numeric(12, 2), server_default="0"),
        sa.Column("balance_due", sa.Numeric(12, 2), server_default="0"),
        sa.Column("invoice_count", sa.Integer(), server_default="0"),
        sa.Column("statement_pdf_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), server_default="unread"),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", sa.String(36), nullable=True),
        sa.Column("dispute_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Statement payments — funeral home pays through platform
    op.create_table(
        "statement_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("received_statement_id", sa.String(36), sa.ForeignKey("received_statements.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("payment_reference", sa.String(200), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("acknowledged_by_manufacturer", sa.Boolean(), server_default="false"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add cross-tenant fields to customer_statements
    op.add_column("customer_statements", sa.Column("cross_tenant_delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_statements", sa.Column("cross_tenant_received_statement_id", sa.String(36), nullable=True))
    op.add_column("customer_statements", sa.Column("payment_received_cross_tenant", sa.Boolean(), server_default="false"))
    op.add_column("customer_statements", sa.Column("payment_amount_cross_tenant", sa.Numeric(12, 2), nullable=True))
    op.add_column("customer_statements", sa.Column("payment_received_at", sa.DateTime(timezone=True), nullable=True))

    # Add platform billing fields to fh_manufacturer_relationships
    op.add_column("fh_manufacturer_relationships", sa.Column("platform_billing_enabled", sa.Boolean(), server_default="false"))
    op.add_column("fh_manufacturer_relationships", sa.Column("platform_billing_enabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("fh_manufacturer_relationships", sa.Column("platform_billing_enabled_by", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("fh_manufacturer_relationships", "platform_billing_enabled_by")
    op.drop_column("fh_manufacturer_relationships", "platform_billing_enabled_at")
    op.drop_column("fh_manufacturer_relationships", "platform_billing_enabled")
    op.drop_column("customer_statements", "payment_received_at")
    op.drop_column("customer_statements", "payment_amount_cross_tenant")
    op.drop_column("customer_statements", "payment_received_cross_tenant")
    op.drop_column("customer_statements", "cross_tenant_received_statement_id")
    op.drop_column("customer_statements", "cross_tenant_delivered_at")
    op.drop_table("statement_payments")
    op.drop_table("received_statements")
