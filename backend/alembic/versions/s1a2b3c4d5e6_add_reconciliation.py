"""Add financial accounts and reconciliation tables.

Revision ID: p1a2b3c4d5e6
Revises: o9a0b1c2d3e4
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op

revision = "s1a2b3c4d5e6"
down_revision = "o9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("account_name", sa.String(100), nullable=False),
        sa.Column("institution_name", sa.String(100), nullable=True),
        sa.Column("last_four", sa.String(4), nullable=True),
        sa.Column("gl_account_id", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        sa.Column("last_reconciled_date", sa.Date(), nullable=True),
        sa.Column("last_reconciled_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_reconciliation_id", sa.String(36), nullable=True),
        sa.Column("credit_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("statement_closing_day", sa.Integer(), nullable=True),
        sa.Column("csv_date_column", sa.String(50), nullable=True),
        sa.Column("csv_description_column", sa.String(50), nullable=True),
        sa.Column("csv_amount_column", sa.String(50), nullable=True),
        sa.Column("csv_debit_column", sa.String(50), nullable=True),
        sa.Column("csv_credit_column", sa.String(50), nullable=True),
        sa.Column("csv_balance_column", sa.String(50), nullable=True),
        sa.Column("csv_date_format", sa.String(20), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("financial_account_id", sa.String(36), sa.ForeignKey("financial_accounts.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="importing"),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("statement_closing_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("total_statement_transactions", sa.Integer(), server_default="0"),
        sa.Column("auto_cleared_count", sa.Integer(), server_default="0"),
        sa.Column("suggested_count", sa.Integer(), server_default="0"),
        sa.Column("unmatched_count", sa.Integer(), server_default="0"),
        sa.Column("opening_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("platform_cleared_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("outstanding_checks_total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("outstanding_deposits_total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("adjustments_total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("difference", sa.Numeric(12, 2), server_default="0"),
        sa.Column("confirmed_by", sa.String(36), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("csv_file_path", sa.Text(), nullable=True),
        sa.Column("csv_row_count", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_recon_runs_status", "reconciliation_runs", ["tenant_id", "status"])

    op.create_table(
        "reconciliation_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("reconciliation_run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_type", sa.String(10), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("raw_description", sa.Text(), nullable=True),
        sa.Column("match_status", sa.String(20), server_default="unmatched"),
        sa.Column("match_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("matched_record_type", sa.String(30), nullable=True),
        sa.Column("matched_record_id", sa.String(36), nullable=True),
        sa.Column("match_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_recon_txn_status", "reconciliation_transactions", ["reconciliation_run_id", "match_status"])

    op.create_table(
        "reconciliation_adjustments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("reconciliation_run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("adjustment_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_record_type", sa.String(30), nullable=True),
        sa.Column("created_record_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("reconciliation_adjustments")
    op.drop_index("idx_recon_txn_status")
    op.drop_table("reconciliation_transactions")
    op.drop_index("idx_recon_runs_status")
    op.drop_table("reconciliation_runs")
    op.drop_table("financial_accounts")
