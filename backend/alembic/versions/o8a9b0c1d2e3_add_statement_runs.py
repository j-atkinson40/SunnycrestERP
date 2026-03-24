"""Add billing profiles and statement run tables.

Revision ID: o8a9b0c1d2e3
Revises: o7a8b9c0d1e2
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "o8a9b0c1d2e3"
down_revision = "o7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add billing profile fields to customers
    op.add_column("customers", sa.Column("billing_profile", sa.String(20), server_default="cod"))
    op.add_column("customers", sa.Column("receives_monthly_statement", sa.Boolean(), server_default="false"))
    op.add_column("customers", sa.Column("payment_terms", sa.String(20), server_default="cod"))
    op.add_column("customers", sa.Column("preferred_delivery_method", sa.String(20), server_default="email"))

    # Add flagging/review columns to existing customer_statements table
    op.add_column("customer_statements", sa.Column("flagged", sa.Boolean(), server_default="false"))
    op.add_column("customer_statements", sa.Column("flag_reasons", JSONB, server_default="[]"))
    op.add_column("customer_statements", sa.Column("review_status", sa.String(20), server_default="pending"))
    op.add_column("customer_statements", sa.Column("reviewed_by", sa.String(36), nullable=True))
    op.add_column("customer_statements", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_statements", sa.Column("review_note", sa.Text(), nullable=True))

    # Add flagged_count to existing statement_runs
    op.add_column("statement_runs", sa.Column("flagged_count", sa.Integer(), server_default="0"))
    op.add_column("statement_runs", sa.Column("approved_by", sa.String(36), nullable=True))
    op.add_column("statement_runs", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    return  # Skip creating tables that already exist


    # Statement runs — one per monthly cycle (ALREADY EXISTS)
    op.create_table(
        "statement_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("total_customers", sa.Integer(), server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), server_default="0"),
        sa.Column("flagged_count", sa.Integer(), server_default="0"),
        sa.Column("sent_count", sa.Integer(), server_default="0"),
        sa.Column("failed_count", sa.Integer(), server_default="0"),
        sa.Column("held_count", sa.Integer(), server_default="0"),
        sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Statement run items — one per customer per run
    op.create_table(
        "statement_run_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("statement_run_id", sa.String(36), sa.ForeignKey("statement_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        # Statement content
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("opening_balance", sa.Numeric(12, 2), server_default="0"),
        sa.Column("invoices_total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("payments_total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("credits_total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("closing_balance", sa.Numeric(12, 2), server_default="0"),
        sa.Column("due_date", sa.Date(), nullable=True),
        # Agent flags
        sa.Column("flagged", sa.Boolean(), server_default="false"),
        sa.Column("flag_reasons", JSONB, server_default="[]"),
        # Review
        sa.Column("review_status", sa.String(20), server_default="pending"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        # Delivery
        sa.Column("delivery_method", sa.String(20), nullable=True),
        sa.Column("delivery_status", sa.String(20), server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        # PDF
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_stmt_items_flagged", "statement_run_items", ["statement_run_id", "flagged"])


def downgrade() -> None:
    op.drop_column("statement_runs", "approved_at")
    op.drop_column("statement_runs", "approved_by")
    op.drop_column("statement_runs", "flagged_count")
    op.drop_column("customer_statements", "review_note")
    op.drop_column("customer_statements", "reviewed_at")
    op.drop_column("customer_statements", "reviewed_by")
    op.drop_column("customer_statements", "review_status")
    op.drop_column("customer_statements", "flag_reasons")
    op.drop_column("customer_statements", "flagged")
    op.drop_column("customers", "preferred_delivery_method")
    op.drop_column("customers", "payment_terms")
    op.drop_column("customers", "receives_monthly_statement")
    op.drop_column("customers", "billing_profile")
