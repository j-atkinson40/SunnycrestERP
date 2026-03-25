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
    # Add billing profile fields to customers (conditionally — some may exist from customer table creation)
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("customers")}

    for col_name, col_def in [
        ("billing_profile", sa.Column("billing_profile", sa.String(20), server_default="cod")),
        ("receives_monthly_statement", sa.Column("receives_monthly_statement", sa.Boolean(), server_default="false")),
        ("payment_terms", sa.Column("payment_terms", sa.String(20), server_default="cod")),
        ("preferred_delivery_method", sa.Column("preferred_delivery_method", sa.String(20), server_default="email")),
    ]:
        if col_name not in existing_cols:
            op.add_column("customers", col_def)

    # Add flagging/review columns to customer_statements IF it exists already
    # (On production it existed before this migration; on fresh DB it won't yet)
    table_names = inspector.get_table_names()

    if "customer_statements" in table_names:
        cs_cols = {c["name"] for c in inspector.get_columns("customer_statements")}
        for col_name, col_def in [
            ("flagged", sa.Column("flagged", sa.Boolean(), server_default="false")),
            ("flag_reasons", sa.Column("flag_reasons", JSONB, server_default="[]")),
            ("review_status", sa.Column("review_status", sa.String(20), server_default="pending")),
            ("reviewed_by", sa.Column("reviewed_by", sa.String(36), nullable=True)),
            ("reviewed_at", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)),
            ("review_note", sa.Column("review_note", sa.Text(), nullable=True)),
        ]:
            if col_name not in cs_cols:
                op.add_column("customer_statements", col_def)

    if "statement_runs" in table_names:
        sr_cols = {c["name"] for c in inspector.get_columns("statement_runs")}
        for col_name, col_def in [
            ("flagged_count", sa.Column("flagged_count", sa.Integer(), server_default="0")),
            ("approved_by", sa.Column("approved_by", sa.String(36), nullable=True)),
            ("approved_at", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)),
        ]:
            if col_name not in sr_cols:
                op.add_column("statement_runs", col_def)

    # Create tables that may not exist yet (fresh DB) — skip if already there (production)
    if "statement_runs" not in table_names:
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

    if "statement_run_items" not in table_names:
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
