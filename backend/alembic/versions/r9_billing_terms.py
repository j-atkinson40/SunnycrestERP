"""Add billing_terms_json to price_list_imports.

Revision ID: r9_billing_terms
Revises: r8_conditional_pricing
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "r9_billing_terms"
down_revision = "r8_conditional_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.add_column is monkey-patched in env.py to be idempotent
    op.add_column(
        "price_list_imports",
        sa.Column("billing_terms_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("price_list_imports", "billing_terms_json")
