"""Add balance_adjustments table

Revision ID: q1k2l3m4n5o6
Revises: p0j1k2l3m4n5
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = "q1k2l3m4n5o6"
down_revision = "p0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "balance_adjustments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id"),
            nullable=False,
        ),
        sa.Column("adjustment_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_balance_adj_customer", "balance_adjustments", ["customer_id"])
    op.create_index("ix_balance_adj_company", "balance_adjustments", ["company_id"])
    op.create_index("ix_balance_adj_created", "balance_adjustments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_balance_adj_created", table_name="balance_adjustments")
    op.drop_index("ix_balance_adj_company", table_name="balance_adjustments")
    op.drop_index("ix_balance_adj_customer", table_name="balance_adjustments")
    op.drop_table("balance_adjustments")
