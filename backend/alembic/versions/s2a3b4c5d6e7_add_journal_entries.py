"""Add journal entries, templates, and accounting periods.

Revision ID: p2a3b4c5d6e7
Revises: p1a2b3c4d5e6
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "s2a3b4c5d6e7"
down_revision = "s1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("entry_number", sa.String(30), nullable=False),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("is_reversal", sa.Boolean(), server_default="false"),
        sa.Column("reversal_of_entry_id", sa.String(36), nullable=True),
        sa.Column("reversal_scheduled", sa.Boolean(), server_default="false"),
        sa.Column("reversal_date", sa.Date(), nullable=True),
        sa.Column("recurring_template_id", sa.String(36), nullable=True),
        sa.Column("corrects_record_type", sa.String(30), nullable=True),
        sa.Column("corrects_record_id", sa.String(36), nullable=True),
        sa.Column("total_debits", sa.Numeric(12, 2), server_default="0"),
        sa.Column("total_credits", sa.Numeric(12, 2), server_default="0"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "entry_number", name="uq_je_number"),
    )
    op.create_index("idx_je_period", "journal_entries", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_je_status", "journal_entries", ["tenant_id", "status"])
    op.create_index("idx_je_date", "journal_entries", ["tenant_id", "entry_date"])

    op.create_table(
        "journal_entry_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("journal_entry_id", sa.String(36), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("gl_account_id", sa.String(36), nullable=False),
        sa.Column("gl_account_number", sa.String(20), nullable=True),
        sa.Column("gl_account_name", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("debit_amount", sa.Numeric(12, 2), server_default="0"),
        sa.Column("credit_amount", sa.Numeric(12, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_je_lines_gl", "journal_entry_lines", ["gl_account_id"])

    op.create_table(
        "journal_entry_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("template_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("months_of_year", JSONB, nullable=True),
        sa.Column("next_run_date", sa.Date(), nullable=True),
        sa.Column("last_run_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("auto_post", sa.Boolean(), server_default="false"),
        sa.Column("auto_reverse", sa.Boolean(), server_default="false"),
        sa.Column("reverse_days_after", sa.Integer(), server_default="1"),
        sa.Column("template_lines", JSONB, server_default="[]"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("closed_by", sa.String(36), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "period_year", "period_month", name="uq_accounting_period"),
    )


def downgrade() -> None:
    op.drop_table("accounting_periods")
    op.drop_table("journal_entry_templates")
    op.drop_index("idx_je_lines_gl")
    op.drop_table("journal_entry_lines")
    op.drop_index("idx_je_date")
    op.drop_index("idx_je_status")
    op.drop_index("idx_je_period")
    op.drop_table("journal_entries")
