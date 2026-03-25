"""Add finance charge system.

Revision ID: q6p7q8r9s0t1
Revises: q5o6p7q8r9s0
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "q6p7q8r9s0t1"
down_revision = "q5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tenant settings
    op.add_column("tenant_settings", sa.Column("finance_charges_enabled", sa.Boolean(), server_default="false"))
    op.add_column("tenant_settings", sa.Column("finance_charge_rate_monthly", sa.Numeric(6, 4), server_default="1.5000"))
    op.add_column("tenant_settings", sa.Column("finance_charge_minimum_amount", sa.Numeric(12, 2), server_default="2.00"))
    op.add_column("tenant_settings", sa.Column("finance_charge_minimum_balance", sa.Numeric(12, 2), server_default="10.00"))
    op.add_column("tenant_settings", sa.Column("finance_charge_balance_basis", sa.String(30), server_default="past_due_only"))
    op.add_column("tenant_settings", sa.Column("finance_charge_compound", sa.Boolean(), server_default="false"))
    op.add_column("tenant_settings", sa.Column("finance_charge_grace_days", sa.Integer(), server_default="0"))
    op.add_column("tenant_settings", sa.Column("finance_charge_calculation_day", sa.Integer(), server_default="27"))
    op.add_column("tenant_settings", sa.Column("finance_charge_gl_account_id", sa.String(36), nullable=True))
    op.add_column("tenant_settings", sa.Column("finance_charge_ar_account_id", sa.String(36), nullable=True))

    # Finance charge runs
    op.create_table(
        "finance_charge_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("run_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="calculated"),
        sa.Column("charge_month", sa.Integer(), nullable=False),
        sa.Column("charge_year", sa.Integer(), nullable=False),
        sa.Column("calculation_date", sa.Date(), nullable=False),
        # Settings snapshot
        sa.Column("rate_applied", sa.Numeric(6, 4), nullable=False),
        sa.Column("balance_basis", sa.String(30), nullable=False),
        sa.Column("compound", sa.Boolean(), nullable=False),
        sa.Column("grace_days", sa.Integer(), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("minimum_balance", sa.Numeric(12, 2), nullable=False),
        # Summary
        sa.Column("total_customers_evaluated", sa.Integer(), server_default="0"),
        sa.Column("total_customers_charged", sa.Integer(), server_default="0"),
        sa.Column("total_customers_forgiven", sa.Integer(), server_default="0"),
        sa.Column("total_customers_below_minimum", sa.Integer(), server_default="0"),
        sa.Column("total_amount_calculated", sa.Numeric(12, 2), server_default="0"),
        sa.Column("total_amount_forgiven", sa.Numeric(12, 2), server_default="0"),
        sa.Column("total_amount_posted", sa.Numeric(12, 2), server_default="0"),
        # Timing
        sa.Column("calculated_by", sa.String(20), server_default="agent"),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_fc_run_month", "finance_charge_runs", ["tenant_id", "charge_year", "charge_month"])

    # Finance charge items
    op.create_table(
        "finance_charge_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("finance_charge_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("eligible_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("rate_applied", sa.Numeric(6, 4), nullable=False),
        sa.Column("calculated_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("minimum_applied", sa.Boolean(), server_default="false"),
        sa.Column("final_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("prior_finance_charge_balance", sa.Numeric(12, 2), server_default="0"),
        sa.Column("aging_snapshot", JSONB, server_default="{}"),
        sa.Column("review_status", sa.String(20), server_default="pending"),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("forgiveness_note", sa.Text(), nullable=True),
        sa.Column("posted", sa.Boolean(), server_default="false"),
        sa.Column("invoice_id", sa.String(36), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Customer fields
    op.add_column("customers", sa.Column("finance_charge_eligible", sa.Boolean(), server_default="true"))
    op.add_column("customers", sa.Column("finance_charge_excluded_reason", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("finance_charge_custom_rate", sa.Numeric(6, 4), nullable=True))

    # Invoice flag
    op.add_column("invoices", sa.Column("is_finance_charge", sa.Boolean(), server_default="false"))


def downgrade() -> None:
    op.drop_column("invoices", "is_finance_charge")
    op.drop_column("customers", "finance_charge_custom_rate")
    op.drop_column("customers", "finance_charge_excluded_reason")
    op.drop_column("customers", "finance_charge_eligible")
    op.drop_table("finance_charge_items")
    op.drop_table("finance_charge_runs")
    for col in [
        "finance_charges_enabled", "finance_charge_rate_monthly",
        "finance_charge_minimum_amount", "finance_charge_minimum_balance",
        "finance_charge_balance_basis", "finance_charge_compound",
        "finance_charge_grace_days", "finance_charge_calculation_day",
        "finance_charge_gl_account_id", "finance_charge_ar_account_id",
    ]:
        op.drop_column("tenant_settings", col)
