"""Add early payment discount system.

Revision ID: q2l3m4n5o6p7
Revises: q1k2l3m4n5o6
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

revision = "q2l3m4n5o6p7"
down_revision = "q1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tenant discount settings
    op.add_column("tenant_settings", sa.Column("early_payment_discount_enabled", sa.Boolean(), server_default="false"))
    op.add_column("tenant_settings", sa.Column("early_payment_discount_percentage", sa.Numeric(5, 2), server_default="2.00"))
    op.add_column("tenant_settings", sa.Column("early_payment_discount_cutoff_day", sa.Integer(), server_default="15"))
    op.add_column("tenant_settings", sa.Column("early_payment_discount_gl_account_id", sa.String(36), nullable=True))

    # Customer discount eligibility
    op.add_column("customers", sa.Column("early_payment_discount_eligible", sa.Boolean(), server_default="true"))
    op.add_column("customers", sa.Column("early_payment_discount_excluded_reason", sa.Text(), nullable=True))

    # Payment discount tracking
    op.add_column("payments", sa.Column("discount_applied", sa.Boolean(), server_default="false"))
    op.add_column("payments", sa.Column("discount_amount", sa.Numeric(12, 2), server_default="0"))
    op.add_column("payments", sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True))
    op.add_column("payments", sa.Column("discount_type", sa.String(20), nullable=True))
    op.add_column("payments", sa.Column("discount_override_by", sa.String(36), nullable=True))
    op.add_column("payments", sa.Column("discount_override_reason", sa.Text(), nullable=True))
    op.add_column("payments", sa.Column("discount_journal_entry_id", sa.String(36), nullable=True))

    # Invoice discount fields
    op.add_column("invoice_lines", sa.Column("discountable", sa.Boolean(), server_default="true"))
    op.add_column("invoices", sa.Column("early_payment_discount_amount", sa.Numeric(12, 2), server_default="0"))
    op.add_column("invoices", sa.Column("early_payment_discounted_total", sa.Numeric(12, 2), nullable=True))

    # Index for discount queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_payments_discount "
        "ON payments(company_id, discount_applied) "
        "WHERE discount_applied = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_payments_discount")
    op.drop_column("invoices", "early_payment_discounted_total")
    op.drop_column("invoices", "early_payment_discount_amount")
    op.drop_column("invoice_lines", "discountable")
    op.drop_column("payments", "discount_journal_entry_id")
    op.drop_column("payments", "discount_override_reason")
    op.drop_column("payments", "discount_override_by")
    op.drop_column("payments", "discount_type")
    op.drop_column("payments", "discount_percentage")
    op.drop_column("payments", "discount_amount")
    op.drop_column("payments", "discount_applied")
    op.drop_column("customers", "early_payment_discount_excluded_reason")
    op.drop_column("customers", "early_payment_discount_eligible")
    op.drop_column("tenant_settings", "early_payment_discount_gl_account_id")
    op.drop_column("tenant_settings", "early_payment_discount_cutoff_day")
    op.drop_column("tenant_settings", "early_payment_discount_percentage")
    op.drop_column("tenant_settings", "early_payment_discount_enabled")
