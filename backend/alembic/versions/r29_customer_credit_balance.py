"""r29_customer_credit_balance

Revision ID: r29_customer_credit_balance
Revises: r28_merge_payment_improvements
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = 'r29_customer_credit_balance'
down_revision = 'r28_merge_payment_improvements'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'customers',
        sa.Column(
            'credit_balance',
            sa.Numeric(12, 2),
            nullable=True,
            server_default='0.00',
        ),
    )


def downgrade():
    op.drop_column('customers', 'credit_balance')
